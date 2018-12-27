# coding=UTF-8

from flask import Flask, render_template, request
import boto3
from threading import Lock, Thread
import os, time
from flask_socketio import SocketIO
import datetime
from queue import Queue
import sys

app = Flask(__name__)

socketio = SocketIO(app)

file_name = None
snapshot_id = None
thread = None
thread_upload = None
thread_lock = Lock()
s3 = None
file_size = 1

queue = Queue()


@app.route("/", methods=['GET', 'POST'])
def awsDemo():
    print('Hello AWS!')
    return render_template('index.html')


@app.route("/upload", methods=['GET'])
def uploadView():
    return render_template('upload.html')


# Section One
# 创建快照
@app.route("/createSnapshot", methods=['POST'])
def createSnapshot():
    print('start getting snapshot...',
          (datetime.datetime.now() + datetime.timedelta(seconds=10)).strftime('%Y-%m-%d %H:%M:%S'))
    ec2 = boto3.client('ec2')
    try:
        snapshot = ec2.create_snapshot(VolumeId='vol-0c1f7bb9048639c9d', Description='aws-demo-task1')

        # get snapshotid
        global snapshot_id
        snapshot_id = snapshot['SnapshotId']
        global COMPLETE
        COMPLETE = False
        getCreateStatus()

        print("Created SnapShot Success!,", snapshot_id)
        print("Finished at", (datetime.datetime.now() + datetime.timedelta(seconds=10)).strftime('%Y-%m-%d %H:%M:%S'))
        return '<p>Created SnapShot Success!</p>' + 'snapshot_id: ' + snapshot_id
    except Exception as e:
        print(e)
        print("Created SnapShot Failed!")
        return 'Created SnapShot Failed!'


@app.route("/complete", methods=['GET'])
def complete():
    global COMPLETE
    COMPLETE = True
    global thread
    thread = None
    print("Complete>>>>>>>>>>>")
    return "complete"


@app.route("/uploadComplete", methods=['GET'])
def uploadComplete():
    global COMPLETE_UPLOAD
    COMPLETE_UPLOAD = True
    global thread_upload
    thread_upload = None
    print("Complete upload >>>>>>>>>>>")
    return "complete upload"


# 发送快照状态(websocket)
# @socketio.on('connect', namespace="/getStatus")
def getCreateStatus():
    global thread
    with thread_lock:
        if thread is None:
            thread = socketio.start_background_task(target=getSnapState)


# 获取快照状态
def getSnapState():
    print('getSnapState' + (datetime.datetime.now() + datetime.timedelta(seconds=10)).strftime('%Y-%m-%d %H:%M:%S'))
    ec2 = boto3.resource('ec2')
    global snapshot_id
    global COMPLETE
    while True and not COMPLETE:
        print("Send progress to client >>> ",
              (datetime.datetime.now() + datetime.timedelta(seconds=10)).strftime('%Y-%m-%d %H:%M:%S'))
        socketio.sleep(0.01)
        snapshot = ec2.Snapshot(snapshot_id)
        progress = snapshot.progress
        state = snapshot.state
        res = {'state': state, 'progress': progress}
        socketio.emit('server_response', {'data': res}, namespace='/getStatus')


class ProgressPercentage(object):
    def __init__(self, filename):
        self._filename = filename
        self._size = float(os.path.getsize(filename))
        self._seen_so_far = 0
        self._lock = Lock()

    def __call__(self, bytes_amount):
        # To simplify we'll assume this is hooked up
        # to a single filename.
        print(" call back start >>>>")
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = (self._seen_so_far / self._size) * 100
            global queue
            queue.put(percentage)
            print(queue.qsize())
            # socketio.emit('server_response', {'data': percentage}, namespace='/getUploadProgress')
            sys.stdout.write(
                "\r%s  %s / %s  (%.2f%%)" % (
                    self._filename, self._seen_so_far, self._size,
                    percentage))
            sys.stdout.flush()


def subtask():
    global queue
    print("sub task >>>>>")
    while True:
        print("queue", queue.get())
        # else:
        #     print("queue empty")


# Section Two
# 上传文件(直接上传)
@app.route("/upload", methods=['POST'])
def upload():
    UPLOAD_FOLDER = os.getcwd() + '/uploads'
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    if request.method == 'POST':
        file = request.files['upload_file']
        global file_name
        file_name = file.filename
        file.save(UPLOAD_FOLDER+"/"+file_name)

        global COMPLETE_UPLOAD
        COMPLETE_UPLOAD = False

        # 调用该方法创建socket多线程任务
        getUploadStatus()

        # 创建线程任务进行上传
        upload_t = Thread(target=uploadThread)
        upload_t.start()
        # uploadThread()
    return "end"


""" 上传线程"""


def uploadThread():
    print('start upload >>>>>>>>>>')
    global COMPLETE_UPLOAD
    COMPLETE_UPLOAD = False
    # 桶名
    bucket = "aws-demo-task"
    UPLOAD_FOLDER = os.getcwd() + '/uploads'
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    # 获取文件
    global file_name
    # file_name = file.filename
    print(file_name)

    # 获取文件地址
    file_path = UPLOAD_FOLDER + '/' + file_name

    # 获取文件大小
    # file.save(file_path)
    global file_size
    file_size = os.path.getsize(os.path.join(UPLOAD_FOLDER, file_name))
    print("file size >>>>>>>>> ", file_size)

    # 获取s3服务
    global s3
    s3 = boto3.client('s3')
    print("creat  s3 success >>>>")
    # 上传文件(获取本地地址)
    s3.upload_file(file_path, bucket, file_name, Callback=ProgressPercentage(file_path))

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
    print('getUploadStatus...')
    global thread_upload
    with thread_lock:
        if thread_upload is None:
            thread_upload = socketio.start_background_task(target=getUploadProgress)


# 获取文件上传进度
def getUploadProgress():
    print("getUploadProgress")
    # bucket_name = "aws-testdemo"
    # upload_size = 0
    global COMPLETE_UPLOAD
    while True and not COMPLETE_UPLOAD:
        socketio.sleep(0.01)
        if queue.qsize() > 0:
            socketio.emit('server_response', {'data': queue.get()}, namespace='/getUploadProgress')


# 获取文件下载链接
@app.route("/getUrl", methods=['GET', 'POST'])
def checkLocation():
    print('getUrl')
    return '<p>Donwload Link</p>' + '<a href="' + url + '">' + url + '</a>'


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
