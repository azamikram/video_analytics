#!/bin/bash

# ./deploy.sh "[AWS_OPTIONS]"

# Reading the following parameters from params.py
S3_buncket_name=$(more params.py | grep bucketName | awk -F'\"' '{print $2}')
Lambda_role_arn=$(more params.py | grep LambdaRoleARN | awk -F'\"' '{print $2}')
Step_role_arn=$(more params.py | grep StepRoleARN | awk -F'\"' '{print $2}')
AWS_account_id=$(more params.py | grep AccountID | awk -F'\"' '{print $2}')

echo "Deploying Split:"
./deploy_split.sh $S3_buncket_name $Lambda_role_arn "$1"

echo "Deploying Extract:"
./deploy_extract.sh $S3_buncket_name $Lambda_role_arn "$1"

echo "Deploying Fanin:"
./deploy_fanin.sh $S3_buncket_name $Lambda_role_arn "$1"

echo "Deploying Classify:"
./deploy_classify.sh $S3_buncket_name $Lambda_role_arn $AWS_account_id "$1"

echo "Upload benchmarking videos"
./upload_videos.sh $S3_buncket_name sample_videos "$1"

./create_state_machine.sh "$1"
