import json
import os.path

from fastapi import FastAPI, File, UploadFile, Request, Security, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import PlainTextResponse

import tdlib_server
from queue_util import QueueUtil

app = FastAPI()
security = HTTPBasic()
templates = Jinja2Templates(directory="templates")

from mylogger import MyLogger

logger = MyLogger("my_logger")

# 挂载第一个静态文件目录
app.mount("/photos", StaticFiles(directory="tdlib/photos", check_dir=False), name="photos")

# 挂载第二个静态文件目录
app.mount("/videos", StaticFiles(directory="tdlib/videos", check_dir=False), name="videos")


@app.on_event("startup")
async def startup_event():
    # for item_ in open('static/wnacg/list.txt').read().split('\n'):
    #     wnacg().down(json.loads(item_)['name'])
    print('启动定时任务')
    # scheduler.start()


@app.on_event("shutdown")
async def shutdown_event():
    print('结束定时任务')
    # scheduler.shutdown()


def render_directory(path: Path, request: Request):
    """
    递归渲染文件夹的函数。
    """
    # 获取文件夹下的文件和子文件夹
    files = []
    folders = []
    for item in path.iterdir():
        if item.is_file():
            files.append(item.name)
        elif item.is_dir():
            folders.append(item.name)

    # 构建HTML响应
    content = f"<h1>文件浏览器</h1><p>当前目录：{path}</p >"
    content += "<h2>返回上级目录：</h2>"
    content += f"<li><a href=' '>..</a ></li>"
    content += "<h2>文件夹：</h2>"
    for folder in folders:
        content += f"<li><a href='{request.url.path}{folder}/'>{folder}</a ></li>"
    content += "<h2>文件：</h2>"
    for file in files:
        content += f"<li><a href='{request.url.path}{file}' download>{file}</a ></li>"
    html = f"<html><body>{content}</body></html>"

    return HTMLResponse(content=html)


# 定义用户名和密码
username = "admin"
password = "12345678WW"


def get_current_username(credentials: HTTPBasicCredentials = Security(security)):
    if credentials.username != username or credentials.password != password:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/")
async def index(request: Request, username: str = Depends(get_current_username)):
    """
    用于渲染文件浏览器的视图函数。
    """
    # 获取当前目录路径
    current_path = Path.cwd()

    return render_directory(current_path, request)


@app.get("/dir/{file_path:path}")
async def browse_directory(file_path: str, request: Request, username: str = Depends(get_current_username)):
    """
    用于浏览文件夹的视图函数。
    """
    # 获取文件夹路径
    path = Path(file_path)
    if path.is_file():
        return FileResponse(file_path)
    return render_directory(path, request)


@app.get("/getChats")
async def read_root():
    """
    获取聊天列表
    :return:
    """
    tdlib_server.td_send({'@type': 'getChats', 'chat_list': None, 'limit': 1000})
    chats = QueueUtil.get_instance().consumer('chats')
    result = []
    for chat_id in chats['chat_ids']:
        tdlib_server.td_send({'@type': 'getChat', 'chat_id': chat_id})
        chat = QueueUtil.get_instance().consumer('chat')
        item = {}
        item['chat_id'] = chat_id
        item['title'] = chat['title']
        result.append(item)
    return result


@app.get("/getChatHistory")
async def read_root(chat_id: int):
    '''
    获取历史
    :param chat_id: 聊天id
    :return:
    '''
    tdlib_server.td_send({'@type': 'loadChats', 'chat_list': [chat_id]})
    tdlib_server.td_send(
        {'@type': 'getChatHistory', 'chat_id': chat_id, 'offset': 0, 'limit': 100, 'only_local': False})
    return QueueUtil.get_instance().consumer('messages')


@app.get("/searchMessagesFilterPhoto")
async def read_root(chat_id: int, offset: int):
    '''
    获取聊天中的图片
    :param chat_id:  聊天id
    :return:
    '''
    # 发送搜索消息的请求
    tdlib_server.td_send(
        {
            "@type": "searchChatMessages",
            "chat_id": chat_id,
            "filter": {
                # "@type": "searchMessagesFilterPhotoAndVideo"  # 仅搜索图片和视频
                "@type": "searchMessagesFilterPhoto"  # 仅搜索图片和视频
            },
            'offset': offset,
            "limit": 100  # 替换为您要返回的消息数量
        }
    )
    foundChatMessages = QueueUtil.get_instance().consumer('foundChatMessages')
    result = []
    for message in foundChatMessages['messages']:
        item = {}
        item['file_id'] = message['content']['photo']['sizes'][-1]['photo']['id']
        item['size'] = message['content']['photo']['sizes'][-1]['photo']['size'] / 1024
        item['date'] = message['date']
        result.append(item)
    return result


@app.get("/searchMessagesFilterVideo")
async def read_root(chat_id: int, offset: int):
    '''
    获取聊天中的视频
    :param chat_id: 聊天id
    :return:
    '''
    from_message_id = 0
    if offset > 0:
        for i in range(offset + 1):
            tdlib_server.td_send(
                {
                    "@type": "searchChatMessages",
                    "chat_id": chat_id,
                    "filter": {
                        "@type": "searchMessagesFilterVideo"  # 仅搜索图片和视频
                        # "@type": "searchMessagesFilterPhoto"  # 仅搜索图片和视频
                    },
                    'from_message_id': from_message_id,
                    'offset': 0,
                    "limit": 100  # 替换为您要返回的消息数量
                }
            )
            foundChatMessages = QueueUtil.get_instance().consumer('foundChatMessages')
            from_message_id = foundChatMessages['next_from_message_id']
    result = []
    save_ = {}
    if os.path.exists('static/file_info.json'):
        save_ = json.loads(open('static/file_info.json').read())
    for message in foundChatMessages['messages']:
        item = {}
        item['preview'] = message['content']['video']['minithumbnail']['data']
        item['caption'] = message['content']['caption']['text']
        item['file_id'] = message['content']['video']['video']['id']
        item['size'] = message['content']['video']['video']['size'] / 1024 / 1024
        item['date'] = message['date']
        result.append(item)
        item['@type'] = str(item['file_id'])
        save_[item['@type']] = item
    with open('static/file_info.json', 'w') as f:
        f.write(json.dumps(save_, ensure_ascii=False))
    return result


@app.get("/downloadFile")
async def read_root(file_id: int):
    '''
    下载文件
    :param file_id: 文件id
    :return:
    '''
    # 发送搜索消息的请求
    file_info = json.loads(open('static/file_info.json').read())
    QueueUtil.get_instance().producer(str(file_id), file_info[str(file_id)])
    return tdlib_server.td_send(
        {'@type': 'downloadFile', 'file_id': file_id, 'priority': 1, 'offset': 0, 'limit': 0, 'synchronous': False})


@app.get("/sendMessage")
async def read_root(chat_id: int, text: str):
    '''
    获取聊天中的视频
    :param chat_id: 聊天id
    :return:
    '''
    # 发送搜索消息的请求
    tdlib_server.td_send(
        {
            "@type": "sendMessage",
            "chat_id": chat_id,
            "message_thread_id": 0,
            "reply_to_message_id": 0,
            "options": None,
            "input_message_content": {
                "@type": "inputMessageText",  # 仅搜索图片和视频
                "disable_web_page_preview": False,
                "text": {
                    '@type': 'formattedText',
                    'text': text
                },
            },
        }
    )
    return QueueUtil.get_instance().consumer('updateMessageSendSucceeded')
