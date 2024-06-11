#!/usr/bin/env python
import os
import re
import time
import math
import subprocess

import boto3
from boto3.s3.transfer import TransferConfig
import params as p

VIDEO_REPO = 'video-repo'
SEGMENTS_REPO = 'video-segments-repo'

FFMPEG_STATIC = "var/ffmpeg"
SEGEMENT_SIZE = 6 # in sec
MIN_BUNDLE_SIZE = 1

ACCESS_KEY_ID = p.accessKeyId
ACCESS_KEY = p.accessKey
BUCKET_NAME = p.bucketName

length_regexp = 'Duration: (\d{2}):(\d{2}):(\d{2})\.\d+,'
re_length = re.compile(length_regexp)

current_time = lambda: round(time.time() * 1000)

def split(vid, start, end, seg_name, upload):
    s_time = current_time()
    local_seg = f"/tmp/{seg_name}"
    subprocess.call([FFMPEG_STATIC, '-hide_banner', '-loglevel', 'error',
                        '-i', vid, '-ss', str(start), '-t', str(end),
                        '-c', 'copy', local_seg])
    upload(seg_name, local_seg)
    os.remove(local_seg)
    return current_time() - s_time

def handler(event, _):
    if('dummy' in event) and (event['dummy'] == 1):
        print("Dummy call, doing nothing")
        return

    s3_client = boto3.client(
        's3',
        aws_access_key_id = ACCESS_KEY_ID,
        aws_secret_access_key = ACCESS_KEY
    )
    config = TransferConfig(use_threads=False)
    upload = lambda key, value: s3_client.upload_file(value,
                                                      BUCKET_NAME,
                                                      f"{SEGMENTS_REPO}/{key}",
                                                      Config=config)

    # Download the source file
    video = "/tmp/src.mp4"
    src = event['src_name']
    key = f"{VIDEO_REPO}/{src}.mp4"
    with open(video, 'wb') as file:
        s3_client.download_fileobj(BUCKET_NAME, key, file, Config=config)
    video_size = os.stat(video).st_size

    output = subprocess.Popen(f"{FFMPEG_STATIC} -i '{video}' 2>&1 | grep 'Duration'",
                              shell = True,
                              stdout = subprocess.PIPE
    ).stdout.read().decode("utf-8")
    matches = re_length.search(output)
    if not matches:
        raise Exception("Couldn't find the duration of the video. Quitting with an error")
    video_length = int(matches.group(1)) * 3600 + \
                    int(matches.group(2)) * 60 + \
                    int(matches.group(3))

    # Split the video in segmants
    start = 0
    split_times = []
    no_segments = 0
    while (start < video_length):
        seg_name = f"{src}_{no_segments}.mp4"
        t = split(video, start, min(video_length - start, SEGEMENT_SIZE), seg_name, upload)
        split_times.append(t)
        no_segments += 1
        start += SEGEMENT_SIZE

    detect_prob = int(event['detect_prob'])
    bundle_size = max(int(event['bundle_size']), MIN_BUNDLE_SIZE)
    base_rsp = {'src': src, 'detect_prob': detect_prob}

    # Bundle segements
    no_bundles = math.ceil(no_segments / bundle_size)
    bundles = [None] * no_bundles
    print(f"Packing {no_segments} segments into {no_bundles} bundles with the size of {bundle_size} each")

    for b_id in range(no_bundles):
        s_seg = b_id * bundle_size
        b_size = min(s_seg + bundle_size, no_segments)
        bundles[b_id] = {**base_rsp,
                         'bundle_id': b_id,
                         'input_sizes': {'split': video_size},
                         'runtimes': {'split': split_times[b_id]},
                         'segments': [seg_id for seg_id in range(s_seg, b_size)]}

    return {'detail': {'indeces': bundles}}
