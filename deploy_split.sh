#!/bin/bash

# ./deploy_split.sh [BUCKET_NAME] [LAMBDA_ROLE_ARN] "[AWS_OPTIONS]"

func_name='split'
cp params.py split/

cd split/var/
tar -xzvf ffprobe.tar.gz
tar -xzvf ffmpeg.tar.gz
cd ../; zip -rqq ../split_package.zip ./*; cd ../

aws $3 s3 cp split_package.zip s3://$1/
aws $3 lambda delete-function --no-cli-pager --function-name $func_name
aws $3 lambda create-function --no-cli-pager \
    --function-name $func_name \
    --runtime python3.12 \
    --role $2 \
    --code "S3Bucket=$1,S3Key=split_package.zip" \
    --handler "fn.handler"
rm split_package.zip

sleep 5
aws $3 lambda update-function-configuration \
    --no-cli-pager \
    --function-name $func_name \
    --memory-size 2048 \
    --timeout 900
aws $1 logs create-log-group --log-group-name "/aws/lambda/${func_name}"
