# coding=UTF-8

from flask import Flask, render_template, request
import boto3
from threading import Lock, Thread
import os, datetime, threading, sys,time
from flask_socketio import SocketIO
from flask_cors import CORS
from queue import Queue
import sys

app = Flask(__name__)

socketio = SocketIO(app)
CORS(app)

file_name = None
snapshot_id = None
thread = None
thread_lock = Lock()
s3 = None
file_size = 1
COMPLETE = False

queue = Queue()


@app.route("/", methods=['GET', 'POST'])
def awsDemo():
    print('Hello AWS!')
    return render_template('index.html')


# Section Two
# 上传文件(直接上传)
# 直接用socketio会导致线程阻塞,不能获取上传进度,通过线程方式开启上传,并使用消息队列返回消息
@app.route("/upload", methods=['POST'])
def upload():
    UPLOAD_FOLDER = os.getcwd() + '/uploads'
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    if request.method == 'POST':
        file = request.files['upload_file']
        global file_name
        file_name = file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], file_name))

        global COMPLETE
        COMPLETE = False

        # 调用该方法创建socket多线程任务
        # global thread
        # thread=None
        getUploadStatus()

        # 创建线程任务进行上传
        upload_t = Thread(target=uploadThread)
        upload_t.start()
        # uploadThread()
    return 'end'


# 上传线程
def uploadThread():
    print('start upload >>>>>>>>>>')
    global COMPLETE
    COMPLETE = False
    # 桶名
    bucket = "aws-testdemo"
    UPLOAD_FOLDER = os.getcwd() + '/uploads'
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    # 获取文件
    global file_name
    print("file name >>>>>>>>> ", file_name)

    # 获取文件地址
    file_path = UPLOAD_FOLDER + '/' + file_name
    # 获取文件大小
    global file_size
    file_size = os.path.getsize(file_path)
    print("file size >>>>>>>>> ", file_size)

    # 获取s3服务
    global s3
    s3 = boto3.client('s3')
    # 上传文件(获取本地地址)
    s3.upload_file(file_path, bucket, file_name, Callback=ProgressPercentage(file_path))
    print("upload finished")

    # 获取下载链接
    global url
    url = s3.generate_presigned_url(
        ClientMethod='get_object',
        Params={
            'Bucket': bucket,
            'Key': file_name
        }
    )


# 发送文件上传进度(websocket)
# @socketio.on('connect', namespace="/getUploadProgress")
def getUploadStatus():
    print("start getUploadStatus thread:  ",
          (datetime.datetime.now() + datetime.timedelta(seconds=10)).strftime('%Y-%m-%d %H:%M:%S'))
    global thread
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(target=getUploadProgress)


# 获取文件上传进度
def getUploadProgress():
    print("getUploadProgress")
    # bucket_name = "aws-testdemo"
    # upload_size = 0
    global COMPLETE
    while True and not COMPLETE:
        socketio.sleep(0.01)
        if queue.qsize() > 0:
            time.sleep(1)
            print(">>>>>>")
            socketio.emit('server_response', {'data': queue.get()}, namespace='/getUploadProgress')


# 回调函数
class ProgressPercentage(object):
    def __init__(self, filename):
        self._filename = filename
        self._size = float(os.path.getsize(filename))
        self._seen_so_far = 0
        self._lock = threading.Lock()

    def __call__(self, bytes_amount):
        # To simplify we'll assume this is hooked up
        # to a single filename.
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = (self._seen_so_far / self._size) * 100
            global queue
            queue.put(percentage)
            # print(queue.qsize())
            sys.stdout.write(
                "\r%s  %s / %s  (%.2f%%)" % (
                    self._filename, self._seen_so_far, self._size,
                    percentage))
            sys.stdout.flush()


# 完成接口
@app.route("/complete", methods=['GET'])
def complete():
    global COMPLETE
    COMPLETE = True
    global thread
    thread = None
    print("Complete>>>>>>>>>>> ",
          (datetime.datetime.now() + datetime.timedelta(seconds=10)).strftime('%Y-%m-%d %H:%M:%S'))
    return "complete"


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
    socketio.run(app, host='0.0.0.0', port=5001)
