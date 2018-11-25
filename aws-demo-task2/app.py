# coding=UTF-8

from flask import Flask, render_template, request
import boto3
from threading import Lock
import os, time
from flask_socketio import SocketIO
from flask_cors import CORS

app = Flask(__name__)

socketio = SocketIO(app)
CORS(app)

file_name = None
snapshot_id = None
thread = None
thread_lock = Lock()
s3 = None
file_size = 1


@app.route("/", methods=['GET', 'POST'])
def awsDemo():
    print('Hello AWS!')
    return render_template('index.html')


# Section Two
# 上传文件(直接上传)
@app.route("/upload", methods=['POST'])
def upload():
    print('upload')
    # 桶名
    bucket = "aws-testdemo"
    UPLOAD_FOLDER = os.getcwd() + '/uploads'
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    try:
        # 获取文件
        if request.method == 'POST':
            file = request.files['upload_file']
            global file_name
            file_name = file.filename

            # 获取文件大小
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], file_name))
            global file_size
            file_path = UPLOAD_FOLDER + '/' + file_name
            file_size = os.path.getsize(file_path)

            # 获取s3服务
            global s3
            s3 = boto3.client('s3')
            # 上传文件(获取本地地址)
            s3.upload_file(file_path, bucket, file_name)

            # 获取下载链接
            global url
            url = s3.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': bucket,
                    'Key': file_name
                }
            )
            return 'File upload Success!'
        else:
            return 'File upload failed!'
    except Exception as e:
        print('Wrong!')
        return 'File upload failed!'


# 发送文件上传进度(websocket)
@socketio.on('connect', namespace="/getUploadProgress")
def getUploadStatus():
    print('getUploadStatus...')
    global thread
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(target=getUploadProgress)


# 完成接口
@app.route("/complete", methods=['GET'])
def complete():
    global COMPLETE
    COMPLETE = True
    global thread
    thread = None
    print("Complete>>>>>>>>>>>")
    return "complete"


# 获取文件上传进度
def getUploadProgress():
    print("getUploadProgress")
    bucket_name = "aws-testdemo"
    upload_size = 0
    while True:
        socketio.sleep(0.01)
        global file_size
        global s3
        if s3 != None:
            resp = s3.list_objects(Bucket=bucket_name)
            # 在桶中的文件中找到已上传的文件大小
            for obj in resp['Contents']:
                if obj['Key'] == file_name:
                    upload_size = obj['Size']
            # 获取原始文件大小
            # 正在上传的文件大小和原始文件大小进度比
            res = format((upload_size / file_size), '0.0%')
            socketio.emit('server_response', {'data': res}, namespace='/getUploadProgress')


# 获取文件下载链接
@app.route("/getUrl", methods=['GET', 'POST'])
def checkLocation():
    print('getUrl')
    return '<p>Donwload Link</p>' + '<a href="' + url + '">' + url + '</a>'


# 分段上传
@app.route("/multiUpload", methods=['POST'])
def multiUpload():
    print('multiUpload')
    bucket_name = "aws-testdemo"
    UPLOAD_FOLDER = os.getcwd() + '/uploads'
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    try:
        # 获取文件及大小
        if request.method == 'POST':
            file = request.files['upload_file']
            global file_name
            file_name = file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], file_name))
            global file_size
            file_size = os.path.getsize(UPLOAD_FOLDER + '/' + file_name)

            # 1. 获取s3服务
            s3 = boto3.client('s3')

            # 2. 初始化multiupload
            multiUploadCreate = s3.create_multipart_upload(Bucket=bucket_name, Key=file_name)
            global uploadId
            uploadId = multiUploadCreate['UploadId']

            # 3. 分块上传
            lst = list()
            part_number = 1
            with open('/Users/natsukashii/Pictures/aws-demo-task1.jpg', 'rb') as fp:
                while True:
                    data = fp.read(1024 * 1024)
                    if data == "":
                        break
                    response = s3.upload_part(
                        Bucket=bucket_name,
                        Key=file_name,
                        UploadId=uploadId,
                        PartNumber=part_number,
                        Body=data
                    )
                    lst.append({'PartNumber': part_number, 'ETag': response['ETag']})
                    part_number += 1

            responsePart = s3.list_parts(
                Bucket=bucket_name,
                Key=file_name,
                UploadId=uploadId
            )

            responseList = s3.list_multipart_uploads(
                Bucket=bucket_name,
            )

            # 4. 完成分块上传
            responseComplete = s3.complete_multipart_upload(
                Bucket=bucket_name,
                Key=file_name,
                UploadId=uploadId,
                MultipartUpload={'Parts': lst}
            )

            print('Upload finished! ' + responseComplete)

            # responseList = s3.list_multipart_uploads(
            #     Bucket=bucket_name,
            # )
            # initiatorID = responseList["Uploads"][0]["Initiator"]["ID"]

            global url
            url = s3.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': file_name
                }
            )
            return 'File upload Success!'
        else:
            return 'File upload Failed!'
    except Exception as e:
        print('Failed!')
        return 'File upload Failed'


if __name__ == '__main__':
    socketio.run()
