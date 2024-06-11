#!/bin/bash

# ./deploy_classify.sh [BUCKET_NAME] [LAMBDA_ROLE_ARN] [AWS_ACCOUNT_ID] "[AWS_OPTIONS]"

func_name='classify'
image_name='video-analytics-image'

cp params.py classify
cd classify/
docker image rm $image_name
docker build -t $image_name .
cd ../

region=$(aws $4 configure get region)
pwd=$(aws $4 ecr get-login-password --region ${region})

aws $4 ecr delete-repository --repository-name $image_name
aws $4 ecr create-repository --repository-name $image_name

docker login -u AWS -p $pwd $3.dkr.ecr.${region}.amazonaws.com
docker tag $image_name:latest $3.dkr.ecr.${region}.amazonaws.com/$image_name:latest
docker push $3.dkr.ecr.${region}.amazonaws.com/$image_name:latest

aws $4 lambda delete-function --no-cli-pager --function-name $func_name
aws $4 lambda create-function --no-cli-pager \
    --function-name $func_name \
    --role $2 \
    --package-type "Image" \
    --code "ImageUri=$3.dkr.ecr.${region}.amazonaws.com/$image_name:latest" \

echo "Sleeping for 1.5 minutes before updating the function's memory size and timeout"
sleep 90

aws $4 lambda update-function-configuration \
    --no-cli-pager \
    --function-name $func_name \
    --memory-size 3008 \
    --timeout 900
aws $1 logs create-log-group --log-group-name "/aws/lambda/${func_name}"
