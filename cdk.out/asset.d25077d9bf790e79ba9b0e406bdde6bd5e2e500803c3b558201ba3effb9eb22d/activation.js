const AWS = require('aws-sdk');
const fs = require('fs');

const s3 = new AWS.S3({});
const stagebucket = process.env.STAGE_BUCKET;

//For CSV generation
var objectToCSVRow = function(dataObject) {
  var dataArray = new Array;
  for (var o in dataObject) {
      var innerValue = dataObject[o]===null?'':dataObject[o].toString();
      var result = innerValue.replace(/"/g, '""');
      //result = '"' + result + '"';
      dataArray.push(result);
  }
  return dataArray.join(',') + '\r\n';
}

//For CSV generation
function toCsv(data){
  console.log("toCsv data=" + JSON.stringify(data));

  let csvContent = '';
  var columns = Object.keys(data[0]);
  csvContent += objectToCSVRow(columns);
  data.forEach(function(item){
    csvContent += objectToCSVRow(item);
  }); 
  return csvContent;
}

//Upload to S3
async function uploadObjectToS3Bucket(bucket, objectName, objectData) {
  const params = {
    Bucket: bucket,
    Key: objectName,
    Body: objectData
  };
  console.log("File uploaded called, objectName=" + objectName);
  try {
      const stored = await s3.upload(params).promise();
      console.log(objectName + " uploaded");
    } catch (err) {
      console.log(objectName + " upload, error=" + err);
    }  
}

//This is where you process the records and call your Partner APIs
async function activate(records){
    
    if(records.length == 0){
      console.debug("activate records - Nothing to process");
      return;      
    }
        
    console.log("Activation bucket=" + stagebucket);

    console.log("*****Partner code start****");
    
    //**************** Start Partner code e.g. call your APIs looping through the records ***//

    //Call your API here

    //Mark records as success or failure
    for (const rec of records) {
      rec.activationStatus = "SUCCESS";      
      //records[1].activationStatus = "FAIL"; //Use for marking records that Failed to process
    }
    
    //*****************End Partner code******************************************************//
      
    //Export the after activation state to activation bucket
    console.log("post records=" + JSON.stringify(records));
    
    today = new Date().toISOString().substring(0, 10);    
    await uploadObjectToS3Bucket(stagebucket, "processed/" + today + ".csv", toCsv(records));

    console.log("*****Partner code end****");
  }


async function fetch(){
  try {
    console.log("fetch called");
    
    //fetch
    var data;
    const params = {
      Bucket: stagebucket,
      Key: 'stage/current.csv'
    };
    
    const file = await s3
    .getObject(params)
    .promise();

    var data = file.Body.toString('utf-8');
    
    // STRING TO ARRAY
    var rows = data.split("\n"); // SPLIT ROWS
    console.log("Total records=" + rows.length);

    header = rows[0].split(","); //SPLIT COLUMNS
    
    records= [];
    rows.forEach(function col(row, rowindex) {
        columns = row.split(","); //Process each row
        if(rowindex !=0 && columns.length > 1){
          //console.log(columns);
          rec = {}
          columns.forEach(function col(val, index){
            //console.log("index=" + index + ",value=" + val);
            rec[header[index]] = val;
          })
          //console.log("rec=" + JSON.stringify(rec));
          records.push(rec);  
        }
    })

    console.log("fetch done, records=" + records.length);

    //Call activation
    await activate(records);    

  } catch (err) {
    console.log("Activation fetch exception=" + err);
    return err
  }
}

exports.handler = async (event, context) => {
  try {
    const data = await fetch();
    return { body: JSON.stringify(data) }
  } catch (err) {
    return { error: err }
  }
}


try {
  const data =  fetch();  
} catch (err) {
  return { error: err }
}
