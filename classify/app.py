import os
import gc
import time
import zipfile
from multiprocessing import Pipe, Process

import boto3
from boto3.s3.transfer import TransferConfig
from imageai.Detection import ObjectDetection
from PIL import Image, ImageFilter, ImageFile
import params as p

ImageFile.LOAD_TRUNCATED_IMAGES = True

FRAMES_REPO = 'video-frames-repo'
DETECTED_OBJECTS_REPO = 'detecte-objects-repo'

YOLO = "/models/yolo-tiny.h5"

ACCESS_KEY_ID = p.accessKeyId
ACCESS_KEY = p.accessKey
BUCKET_NAME = p.bucketName

def delete_tmp():
    for root, dirs, files in os.walk("/tmp/", topdown=False):
       for name in files:
          os.remove(os.path.join(root, name))
       for name in dirs:
          os.rmdir(os.path.join(root, name))

def crop_and_sharpen(original_image, t, objs ,start_index, end_index, worker_dir):
    for box in range(start_index, end_index):
        original_image.crop((objs[box]['box_points'][0],
                             objs[box]['box_points'][1],
                             objs[box]['box_points'][2],
                             objs[box]['box_points'][3])).\
                            resize((1408, 1408)).\
                            filter(ImageFilter.SHARPEN).\
                            save(f"{worker_dir}/{objs[box]['name']}_{box}_{t}.jpg")

    gc.collect()
    return

def detect_object(src, frame, detect_prob, conn):
    s_time = round(time.time() * 1000)

    s3_client = boto3.client(
        's3',
        aws_access_key_id = ACCESS_KEY_ID,
        aws_secret_access_key = ACCESS_KEY
    )
    config = TransferConfig(use_threads=False)
 
    worker_dir = f"/tmp/{src}_{frame}"
    if not os.path.exists(worker_dir):
        os.mkdir(worker_dir)



    # Download the frame
    filename = f"{worker_dir}/frame.jpg"
    key = f"{FRAMES_REPO}/{src}_{frame}.jpg"
    with open(filename, 'wb') as file:
        print(f'============================  {BUCKET_NAME} | {key} | {file}')
        s3_client.download_fileobj(BUCKET_NAME, key, file, Config=config)

    # Detect objects
    output_path = f"/images/out_{src}_{frame}.jpg"
    detector = ObjectDetection()
    detector.setModelTypeAsTinyYOLOv3()
    detector.setModelPath(YOLO)
    detector.loadModel()
    objects = detector.detectObjectsFromImage(input_image=filename,
                                              output_image_path=output_path,
                                              minimum_percentage_probability=detect_prob)
    del detector
    gc.collect()

    if (len(objects) > 10):
        original_image = Image.open(filename, mode='r')
        ths = []
        threads = 10
        start_index = 0
        step_size = int(len(objects) / threads) + 1
        for t in range(threads):
            end_index = min(start_index + step_size , len(objects))
            ths.append(Process(target=crop_and_sharpen, args=(original_image, t,
                                                                objects, start_index,
                                                                end_index, worker_dir)))
            start_index = end_index

        for t in range(threads):
            ths[t].start()
        for t in range(threads):
            ths[t].join()
        for t in range(threads):
            ths[t].kill()

        original_image.close()
        del original_image
        del ths
        gc.collect()

    # Zip all the objects
    zipFilename = f"/tmp/detected_objs_{src}_{frame}.zip"
    zip = zipfile.ZipFile(zipFilename, 'w', zipfile.ZIP_DEFLATED)
    for f in os.listdir(worker_dir):
        zip.write(f"{worker_dir}/{f}")
    zip.close()

    # Upload the zip
    key = f"{DETECTED_OBJECTS_REPO}/{os.path.basename(zipFilename)}"
    s3_client.upload_file(zipFilename, BUCKET_NAME, key, Config=config)

    del objects
    del config
    del s3_client

    conn.send((round(time.time() * 1000) - s_time, os.stat(filename).st_size))

def handler(event, _):
    if('dummy' in event) and (event['dummy'] == 1):
        print("Dummy call, doing nothing")
        return

    s_time = round(time.time() * 1000)

    src = event['src']
    frames = event['frames']
    runtimes = event['runtimes']
    bundle_id = event['bundle_id']
    input_sizes = event['input_sizes']
    detect_prob = event['detect_prob']

    no_frames = len(frames)
    print(f"Processing bundle id {bundle_id} with {no_frames} frames...")

    if (no_frames > 1):
        raise Exception('Current implementation does not allow bundle size > 1')

    pool = [None] * no_frames
    conn = [None] * no_frames
    for i, f in enumerate(frames):
        rcvr, sndr = Pipe(duplex=False)
        conn[i] = rcvr
        pool[i] = Process(target=detect_object, args=(src, f, detect_prob, sndr))
        pool[i].start()

    f_size = 0
    for i, f in enumerate(frames):
        pool[i].join()
        _, f_size = conn[i].recv()
        pool[i].kill()

    delete_tmp()
    gc.collect()

    l_runtime = round(time.time() * 1000) - s_time
    return {
        'src': src,
        'frames': frames,
        'bundle_id': bundle_id,
        'runtimes': {**runtimes, 'classify': l_runtime},
        'input_sizes': {**input_sizes, 'classify': f_size}
    }
