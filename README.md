## Introduction

This is a sample Video Analytics application for AWS Lambda. The goal is to deploy a small set of functions (also known as serverless workload or serverless DAG) on AWS Lambda. The code is adopted from [Orion](https://github.com/icanforce/Orion-OSDI22?tab=readme-ov-file#getting-started).

## Setup and Execution

```
git clone https://github.com/azamikram/video_analytics.git
cd video_analytics/src
```

Make sure that `aws` is configured with your account. For detailed guide on how to setup a AWS account and the associated account, please refer to [Orion](https://github.com/icanforce/Orion-OSDI22?tab=readme-ov-file#getting-started).

After setting up the AWS account, you should be able to populate `params.py`. There is a sample file named `params.py.example`, modify it's name to `params.py` and add the required parameters. Once everything is setup, you can deploy the application on AWS Lambda.

```
./deploy.sh
```

`deploy.sh` will deploy all the functions to Lambda, create a step function to execute the application, and upload a few sample videos on S3. Now you should be able to execute the application
using the AWS protal.

Go to `Step Functions` from the AWS portal and you should be able to see a state machine named `video_sm`. You can use the following json to test an execution.

```json
{"src_name": 0, "bundle_size": 1, "detect_prob": 2}
```

The output of all the function will be uploaded to your S3 bucket. For the final output, checkout `detecte-objects-repo`.

### Gotcha
The classify function first creates a docker image and then deployes that docker image to AWS Lambda. You either need to modify `deploy_classify.sh` to use `docker` with `sudo` or [add your user to the docker group](https://stackoverflow.com/questions/48957195/how-to-fix-docker-got-permission-denied-issue).

