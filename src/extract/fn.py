#!/usr/bin/env python

import os
import time
import subprocess
from multiprocessing import Pipe, Process

import boto3
from boto3.s3.transfer import TransferConfig
import params as p

SEGMENTS_REPO = 'video-segments-repo'
FRAMES_REPO = 'video-frames-repo'

FFMPEG_STATIC = "var/ffmpeg"
DEFAULT_FRAME = 'var/default_frame.jpg'

ACCESS_KEY_ID = p.accessKeyId
ACCESS_KEY = p.accessKey
BUCKET_NAME = p.bucketName

def process_seg(src, seg, conn):
    s_time = round(time.time() * 1000)

    s3_client = boto3.client(
        's3',
        aws_access_key_id = ACCESS_KEY_ID,
        aws_secret_access_key = ACCESS_KEY
    )
    config = TransferConfig(use_threads=False)

    # Downlaod the segement
    filename = f"/tmp/seg_{seg}.mp4"
    key = f"{SEGMENTS_REPO}/{src}_{seg}.mp4"
    with open(filename, 'wb') as file:
        s3_client.download_fileobj(BUCKET_NAME, key, file, Config=config)
    seg_size = os.stat(filename).st_size

    # Extract the median i-frame
    frame_name = f"{src}_{seg}.jpg"
    l_frame = f"/tmp/{frame_name}"
    subprocess.call([FFMPEG_STATIC, '-i', filename, '-frames:v', "1" , "-q:v","1", l_frame])

    # Upload the extracted frame if any
    key = f"{FRAMES_REPO}/{frame_name}"
    try:
        s3_client.upload_file(l_frame, BUCKET_NAME, key, Config=config)
        os.remove(l_frame)
    except:
        s3_client.upload_file(DEFAULT_FRAME, BUCKET_NAME, key, Config=config)

    os.remove(filename)
    conn.send((round(time.time() * 1000) - s_time, seg_size))

def handler(event, _):
    if('dummy' in event) and (event['dummy'] == 1):
       print("Dummy call, doing nothing")
       return

    src = event['src']
    bundle_id = event['bundle_id']
    runtimes = event['runtimes']
    input_sizes = event['input_sizes']
    segments = event['segments']
    detect_prob = int(event['detect_prob'])

    no_seg = len(segments)
    print(f"Processing bundle id {bundle_id} with {no_seg} segments...")

    if (no_seg > 1):
        raise Exception('Current implementation does not allow bundle size > 1')

    pool = [None] * no_seg
    conn = [None] * no_seg
    for i, seg in enumerate(segments):
        rcvr, sndr = Pipe(duplex=False)
        conn[i] = rcvr
        pool[i] = Process(target=process_seg, args=(src, seg, sndr))
        pool[i].start()

    frames = [None] * no_seg
    new_size = 0
    new_runtime = 0
    for i in range(no_seg):
        pool[i].join()
        seg_time, seg_size = conn[i].recv()
        frames[i] = segments[i]
        new_size = {**input_sizes, 'extract': seg_size}
        new_runtime = {**runtimes, 'extract': seg_time}

    for i in range(no_seg):
        pool[i].kill()

    return {
        'src': src,
        'frames': frames,
        'bundle_id': bundle_id,
        'runtimes': new_runtime,
        'input_sizes': new_size,
        'detect_prob': detect_prob,
    }
