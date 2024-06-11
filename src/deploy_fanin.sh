#!/bin/bash

# ./deploy_fanin.sh [BUCKET_NAME] [LAMBDA_ROLE_ARN] "[AWS_OPTIONS]"

func_name='fanin'
cd $func_name && zip -rqq ../fanin_package.zip ./*; cd ../

aws $3 s3 cp fanin_package.zip s3://$1/
aws $3 lambda delete-function --no-cli-pager --function-name $func_name
aws $3 lambda create-function --no-cli-pager \
    --function-name $func_name \
    --runtime python3.12 \
    --role $2 \
    --code "S3Bucket=$1,S3Key=fanin_package.zip" \
    --handler "fn.handler"
rm fanin_package.zip
sleep 1

aws $3 lambda update-function-configuration \
    --no-cli-pager \
    --function-name $func_name \
    --memory-size 1024 \
    --timeout 900
aws $1 logs create-log-group --log-group-name "/aws/lambda/${func_name}"
