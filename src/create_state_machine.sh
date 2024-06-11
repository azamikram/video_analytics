#!/bin/bash

# ./create_state_machine.sh "[AWS_OPTIONS]"

step_role_arn=$(more params.py | grep StepRoleARN | awk -F'\"' '{print $2}')
split_arn=$(aws $1 lambda get-function --function-name split --output json | grep FunctionArn | awk -F'Arn\": "' '{print $2}' | awk -F'"' '{print $1}')
extract_arn=$(aws $1 lambda get-function --function-name extract --output json | grep FunctionArn | awk -F'Arn\": "' '{print $2}' | awk -F'"' '{print $1}')
fanin_arn=$(aws $1 lambda get-function --function-name fanin --output json | grep FunctionArn | awk -F'Arn\": "' '{print $2}' | awk -F'"' '{print $1}')
classify_arn=$(aws $1 lambda get-function --function-name classify --output json | grep FunctionArn | awk -F'Arn\": "' '{print $2}' | awk -F'"' '{print $1}')

sm_name='video_sm'
sm_arn=$(aws $1 stepfunctions list-state-machines \
            --no-cli-pager \
            --query "stateMachines[?name=='$sm_name'].stateMachineArn" \
            | grep "$sm_name" | tr -d '"')

echo 'Deleting the old state machine if exists...'
aws $1 stepfunctions delete-state-machine --state-machine-arn $sm_arn && sleep 30

echo "Creating new state machine..."

STATE_MACHINE=$(cat <<EOF
    {
        "Comment": "Video Analytics DAG",
        "StartAt": "split",
        "States": {
            "split": {
                "Type": "Task",
                "Resource": "$split_arn",
                "Next": "extract_map"
                },

            "extract_map" : {
                "Type": "Map",
                "InputPath": "$.detail",
                "ItemsPath": "$.indeces",
                "MaxConcurrency": 100,
                "Iterator": {
                    "StartAt": "extract",
                    "States": {
                        "extract": {
                            "Type" : "Task",
                            "Resource": "$extract_arn",
                            "End": true
                            }
                        }
                    },
                "Next": "extract_fanin"
            },

            "extract_fanin": {
                "Type": "Task",
                "Resource": "$fanin_arn",
                "Next": "classify_map"
            },

            "classify_map" : {
                "Type": "Map",
                "InputPath": "$.detail",
                "ItemsPath": "$.indeces",
                "MaxConcurrency": 100,
                "Iterator": {
                    "StartAt": "classify",
                    "States": {
                        "classify": {
                            "Type" : "Task",
                            "Resource": "$classify_arn",
                            "End": true
                        }
                    }
                },
                "End": true
            }
        }
    }
EOF
)

aws $1 logs delete-log-group --log-group-name "${sm_name}_log_group"
aws $1 logs create-log-group --log-group-name "${sm_name}_log_group"
log_group_arn=$(aws $1 logs describe-log-groups --log-group-name-prefix "${sm_name}_log_group" --output json | grep arn | awk -F'arn\": "' '{print $2}' | awk -F'"' '{print $1}')

LOGGING_INFO=$(cat <<EOF
    {
        "level": "ALL",
        "includeExecutionData": true,
        "destinations": [
            {
                "cloudWatchLogsLogGroup": {"logGroupArn": "$log_group_arn"}
            }
        ]
    }
EOF
)

aws $1 stepfunctions create-state-machine \
    --no-cli-pager \
    --type EXPRESS \
    --name $sm_name \
    --definition "$STATE_MACHINE" \
    --role-arn $step_role_arn \
    --logging-configuration "$LOGGING_INFO"
