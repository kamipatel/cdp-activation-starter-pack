import { Stack, StackProps, Duration, aws_events as events, aws_events_targets as eventTargets, aws_stepfunctions as sfn, aws_stepfunctions_tasks as tasks, aws_events_targets as targets, aws_iam as iam, CfnParameter, aws_s3 as s3, aws_logs as logs} from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as eventsTarget from 'aws-cdk-lib/aws-events-targets';
import console = require('console');
import * as path from 'path';

export class CdpAwsStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const CDP_BUCKET_NAME = new CfnParameter(this, 'CDP_BUCKET_NAME', {
      type: 'String',
      description: 'CDP In existing bucket name',
      default: '',
      maxLength: 100
    });
    let cdp_in_existing_bucket = null;
    let cdp_in_existing_bucket_name = "";
    if(CDP_BUCKET_NAME != null && CDP_BUCKET_NAME.valueAsString.length > 0){
      cdp_in_existing_bucket_name = CDP_BUCKET_NAME.valueAsString;
      console.log('cdp_in_bucket 👉 ', cdp_in_existing_bucket_name);
      cdp_in_existing_bucket = s3.Bucket.fromBucketName(this,cdp_in_existing_bucket_name, cdp_in_existing_bucket_name);
    }

    /*********** where is functions buckets  ***********/  
    var tmplBucketName = 'cdp-pub-' + this.region;
    //tmplBucketName = "pi-pub-ap-northeast-1";
    console.log("tmplBucketName  is=" + tmplBucketName);
    const bucket = s3.Bucket.fromBucketName(this,tmplBucketName, tmplBucketName);
    console.log("template bucket is=" + bucket);
    const functionszip = 'functions.zip';
    
    /*********** S3 buckets  ***********/  
    const cdpDataInBucket = new s3.Bucket(this, 'cdp-data-in-bucket', {
      versioned: false,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL
    });
    const cdpDataStageBucket = new s3.Bucket(this, 'cdp-data-stage-bucket', {
      versioned: false,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL
    });
    const cdpDataSummaryBucket = new s3.Bucket(this, 'cdp-data-summary-bucket', {
      versioned: false,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL
    });
    const cdpDataFakeBucket = new s3.Bucket(this, 'cdp-data-fake-bucket', {
      versioned: false,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL
    });

    /*********** Lambda  ***********/  
    const piAwsWranglerLayer = new lambda.LayerVersion(this, 'pi-aws-wrangler-layer', {
      compatibleRuntimes: [
        lambda.Runtime.PYTHON_3_8,
      ],      
      code: lambda.Code.fromBucket(bucket, "awswrangler-layer-2.10.0-py3.8.zip"),
      description: 'aws datawrangler library',
    });

  const stageInfoFunctionMemorySize = 2048;    
  const stageInfoDataHandler = new lambda.Function(this, "cdp-stage-info", {
    runtime: lambda.Runtime.PYTHON_3_8, 
    code: lambda.Code.fromAsset(path.join(__dirname, './../src')),      
    handler: "stage-info.lambda_handler",
    environment: {
      IN_BUCKET: cdpDataInBucket.bucketName,
      STAGE_BUCKET: cdpDataStageBucket.bucketName,
      EXISTING_BUCKET: cdp_in_existing_bucket_name,
      FAKE_BUCKET: cdpDataFakeBucket.bucketName,
      REGION: this.region
    },
    functionName: 'cdp-stage-info',
    layers: [piAwsWranglerLayer],
    timeout: Duration.minutes(14),      
    memorySize: stageInfoFunctionMemorySize
  });      
  cdpDataInBucket.grantRead(stageInfoDataHandler); 
  cdpDataStageBucket.grantReadWrite(stageInfoDataHandler); 
  cdpDataFakeBucket.grantRead(stageInfoDataHandler); 
  if(cdp_in_existing_bucket != null){
    cdp_in_existing_bucket.grantRead(stageInfoDataHandler); 
  }

  const stageAccountFunctionMemorySize = 2048;    
  const stageAccountDataHandler = new lambda.Function(this, "cdp-stage-account", {
    runtime: lambda.Runtime.PYTHON_3_8, 
    code: lambda.Code.fromAsset(path.join(__dirname, './../src')),      
    handler: "stage-account.lambda_handler",
    environment: {
      IN_BUCKET: cdpDataInBucket.bucketName,
      STAGE_BUCKET: cdpDataStageBucket.bucketName,
      EXISTING_BUCKET: cdp_in_existing_bucket_name,
      FAKE_BUCKET: cdpDataFakeBucket.bucketName,
      REGION: this.region
    },
    functionName: 'cdp-stage-account',
    layers: [piAwsWranglerLayer],
    timeout: Duration.minutes(14),      
    memorySize: stageAccountFunctionMemorySize
  });      
  cdpDataInBucket.grantRead(stageAccountDataHandler); 
  cdpDataStageBucket.grantReadWrite(stageAccountDataHandler); 
  cdpDataFakeBucket.grantRead(stageAccountDataHandler); 
  if(cdp_in_existing_bucket != null){
    cdp_in_existing_bucket.grantRead(stageAccountDataHandler); 
  }

    const activationFunctionMemorySize = 2048;    
    const activationLambdaFunction = new lambda.Function(this, 'cdp-activation', {
      runtime: lambda.Runtime.PYTHON_3_8, 
      code: lambda.Code.fromAsset(path.join(__dirname, './../src')),      
      handler: 'activation.lambda_handler',
      environment: {
        STAGE_BUCKET: cdpDataStageBucket.bucketName,
        REGION: this.region,
      },
      functionName: 'cdp-activation',
      layers: [piAwsWranglerLayer],      
      timeout: Duration.minutes(14),      
      memorySize: activationFunctionMemorySize
    }); 
    cdpDataStageBucket.grantReadWrite(activationLambdaFunction); 

    const summaryFunctionMemorySize = 2048;    
    const summaryDataHandler = new lambda.Function(this, "cdp-summary", {
      runtime: lambda.Runtime.PYTHON_3_8, 
      code: lambda.Code.fromAsset(path.join(__dirname, './../src')),      
      handler: "summary.lambda_handler",
      environment: {
        SUMMARY_BUCKET: cdpDataSummaryBucket.bucketName,
        REGION: this.region,
      },
      functionName: 'cdp-summary',
      timeout: Duration.minutes(14),
      layers: [piAwsWranglerLayer],
      memorySize: summaryFunctionMemorySize,
    });      
    cdpDataSummaryBucket.grantReadWrite(summaryDataHandler); 

    const fakeInfoFunctionMemorySize = 1024;    
    const fakeInfoHandler = new lambda.Function(this, "cdp-fake-info", {
      runtime: lambda.Runtime.PYTHON_3_8, 
      code: lambda.Code.fromAsset(path.join(__dirname, './../src')),      
      handler: "fake-info.lambda_handler",
      environment: {
        FAKE_BUCKET: cdpDataFakeBucket.bucketName,
        REGION: this.region,
      },
      functionName: 'cdp-fake-info',
      layers: [piAwsWranglerLayer],
      timeout: Duration.minutes(14),      
      memorySize: fakeInfoFunctionMemorySize
    });      
    cdpDataFakeBucket.grantReadWrite(fakeInfoHandler); 

    const fakeAccountFunctionMemorySize = 2048;    
    const fakeAccountHandler = new lambda.Function(this, "cdp-fake-account", {
      runtime: lambda.Runtime.PYTHON_3_8, 
      code: lambda.Code.fromAsset(path.join(__dirname, './../src')),      
      handler: "fake-account.lambda_handler",
      environment: {
        FAKE_BUCKET: cdpDataFakeBucket.bucketName,
        REGION: this.region,
      },
      functionName: 'cdp-fake-account',
      layers: [piAwsWranglerLayer],
      timeout: Duration.minutes(14),      
      memorySize: fakeAccountFunctionMemorySize
    });      
    cdpDataFakeBucket.grantReadWrite(fakeAccountHandler); 

    const queryFunctionMemorySize = 2048;    
    const queryLambdaFunction = new lambda.Function(this, 'cdp-query', {
      runtime: lambda.Runtime.PYTHON_3_8, 
      code: lambda.Code.fromAsset(path.join(__dirname, './../src')),      
      handler: 'query.lambda_handler',
      environment: {
        STAGE_BUCKET: cdpDataStageBucket.bucketName,
        REGION: this.region,
      },
      functionName: 'cdp-query',
      layers: [piAwsWranglerLayer],      
      timeout: Duration.minutes(14),      
      memorySize: queryFunctionMemorySize
    }); 
    

    //Let's create a Step function
    const stageInfoTask= new tasks.LambdaInvoke(this, 'Stage Info', {
      lambdaFunction: stageInfoDataHandler
    });
    const stageAccountTask= new tasks.LambdaInvoke(this, 'Stage Account', {
      lambdaFunction: stageAccountDataHandler
    });
    const stageWorkflowSuccess = new sfn.Succeed(this, 'Stage Workflow complete!');

    const fakeInfoTask= new tasks.LambdaInvoke(this, 'Fake Info', {
      lambdaFunction: fakeInfoHandler
    });
    const fakeAccountTask= new tasks.LambdaInvoke(this, 'Fake Account', {
      lambdaFunction: fakeAccountHandler
    });    
    const fakeWorkflowSuccess = new sfn.Succeed(this, 'Fake Workflow complete!');

    //Satge state machine
    const stageInfoChain = stageAccountTask;
    const stageAccountsMap = new sfn.Map(this, 'stageAccountsMap', {
      itemsPath: '$.Payload.body.unique_accounts',      
      maxConcurrency: 5,
      parameters: {
        "index.$": "$$.Map.Item.Index",
        "account.$": "$$.Map.Item.Value",
        "dt.$": "$.Payload.body.latest_date",
        "data.$": "$.Payload.body"
      }
    }).
    iterator(stageInfoChain)
  
    const stageChain = stageInfoTask
    .next(stageAccountsMap)
    .next(stageWorkflowSuccess)
   
    const stageStateMachine = new sfn.StateMachine(this, 'cdp-stage-statemachine', {
      definition: stageChain,
      timeout: Duration.hours(3),
    });

    //Satge state machine
    const fakeInfoChain = fakeAccountTask;
    const fakeAccountsMap = new sfn.Map(this, 'fakeAccountsMap', {
      itemsPath: '$.Payload.body.accounts',      
      maxConcurrency: 5,
      parameters: {
        "index.$": "$$.Map.Item.Index",
        "account.$": "$$.Map.Item.Value",
        "total_segments.$": "$.Payload.body.total_segments",
        "total_activations.$": "$.Payload.body.total_activations",
        "chunk_size.$": "$.Payload.body.chunk_size"        
      }
    }).
    iterator(fakeInfoChain)
  
    const fakeChain = fakeInfoTask
    .next(fakeAccountsMap)
    .next(fakeWorkflowSuccess)
   
    const fakeStateMachine = new sfn.StateMachine(this, 'cdp-fake-statemachine', {
      definition: fakeChain,
      timeout: Duration.hours(3),
    });
    
    const stageRule = new events.Rule(this, 'cdp-stage-schedule', {
      schedule: events.Schedule.rate(Duration.hours(24)),
      targets: [new eventTargets.SfnStateMachine(stageStateMachine)]
    });


  /******************Create users */
  const cdpDataInBucketAccessPolicy = new iam.Policy(this, 'CdpDataInUserPolicy', {
    document: new iam.PolicyDocument({
      statements: [
        new iam.PolicyStatement({ // Restrict to listing and writing tables
          actions: ['s3:PutObject', 's3:ListBucket'],
          resources: [cdpDataInBucket.bucketArn],
        })
      ]})
    });    
    const cdpDataStageBucketAccessPolicy = new iam.Policy(this, 'cdpDataStageBucketAccessPolicy', {
      document: new iam.PolicyDocument({
        statements: [
          new iam.PolicyStatement({ // Restrict to listing and describing tables
            actions: ['s3:GetObject', 's3:ListBucket'],
            resources: [cdpDataStageBucket.bucketArn],
          })
        ]})
      });    
      const cdpDataSummaryBucketAccessPolicy = new iam.Policy(this, 'cdpDataSummaryBucketAccessPolicy', {
        document: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({ // Restrict to listing and describing tables
              actions: ['s3:GetObject', 's3:ListBucket'],
              resources: [cdpDataSummaryBucket.bucketArn],
            })
          ]})
        });    

    const group = new iam.Group(this, 'cdp-group');
    const cdpDataInUser = new iam.User(this, 'cdpDataInUser', {});
    cdpDataInBucketAccessPolicy.attachToUser(cdpDataInUser);

    const cdpDataStageUser = new iam.User(this, 'cdpDataStageUser', {});
    cdpDataStageBucketAccessPolicy.attachToUser(cdpDataStageUser);
    cdpDataSummaryBucketAccessPolicy.attachToUser(cdpDataStageUser);

  }
  
}

