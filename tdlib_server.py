import os
import threading
from ctypes.util import find_library
from ctypes import *
import json
import sys
import platform

system_type = platform.system()

# 加载共享库
from queue_util import QueueUtil

tdjson_path = None
if system_type == 'Darwin':
    tdjson_path = find_library('tdjson') or 'static/libtdjson.1.8.15.dylib'
elif system_type == 'Linux':
    tdjson_path = find_library('tdjson') or '/app/static/libtdjson.so'
if tdjson_path is None:
    sys.exit("找不到 'tdjson' 库")
tdjson = CDLL(tdjson_path)

# 从共享库中加载TDLib函数
_td_create_client_id = tdjson.td_create_client_id
_td_create_client_id.restype = c_int
_td_create_client_id.argtypes = []

_td_receive = tdjson.td_receive
_td_receive.restype = c_char_p
_td_receive.argtypes = [c_double]

_td_send = tdjson.td_send
_td_send.restype = None
_td_send.argtypes = [c_int, c_char_p]

_td_execute = tdjson.td_execute
_td_execute.restype = c_char_p
_td_execute.argtypes = [c_char_p]

log_message_callback_type = CFUNCTYPE(None, c_int, c_char_p)

_td_set_log_message_callback = tdjson.td_set_log_message_callback
_td_set_log_message_callback.restype = None
_td_set_log_message_callback.argtypes = [c_int, log_message_callback_type]


# 初始化TDLib日志
@log_message_callback_type
def on_log_message_callback(verbosity_level, message):
    if verbosity_level == 0:
        sys.exit('TDLib致命错误: %r' % message)


def td_execute(query):
    query = json.dumps(query).encode('utf-8')
    result = _td_execute(query)
    if result:
        result = json.loads(result.decode('utf-8'))
    return result


_td_set_log_message_callback(2, on_log_message_callback)

# 设置TDLib日志的详细程度为1（仅显示错误）
print(str(td_execute({'@type': 'setLogVerbosityLevel', 'new_verbosity_level': 1, '@extra': 1.01234})).encode('utf-8'))

# 创建客户端
client_id = _td_create_client_id()


# 客户端使用的简单封装函数
def td_send(query):
    query = json.dumps(query).encode('utf-8')
    _td_send(client_id, query)


def td_receive():
    result = _td_receive(1.0)
    if result:
        result = json.loads(result.decode('utf-8'))
    return result


# TDLib execute方法的另一个测试
print(str(td_execute({'@type': 'getTextEntities', 'text': '@telegram /test_command https://telegram.org telegram.me',
                      '@extra': ['5', 7.0, 'a']})).encode('utf-8'))


# 获取历史
# td_send({'@type': 'getChatHistory', 'chat_id': 6264472862, 'offset': 0, 'limit': 100, 'only_local': False})
# 下载文件
# td_send({'@type': 'downloadFile', 'file_id': 1337, 'priority': 1, 'offset': 0, 'limit': 0, 'synchronous': False})
# td_send({'@type': 'getChats', 'chat_list': None, 'limit': 1000})
# td_send({'@type': 'loadChats', 'chat_list': None})

def start():
    # 发送请求启动客户端
    td_send({'@type': 'getOption', 'name': 'version', '@extra': 1.01234})
    td_send(
        {'@type': 'addProxy', 'server': '100.124.132.135', 'port': 8099, 'enable': True,
         'type': {'@type': 'proxyTypeSocks5'}}
    )
    td_send({'@type': 'enableProxy', 'proxy_id': '2'})
    # td_send({'@type': 'proxy', 'server': '100.124.132.135', 'port': 8099,'is_enabled':True,'type':'socks5'})
    # 主事件循环
    while True:
        event = td_receive()
        if event:
            # 处理授权状态
            if event['@type'] == 'updateAuthorizationState':
                auth_state = event['authorization_state']

                # 如果客户端已关闭，需要销毁并创建新的客户端
                if auth_state['@type'] == 'authorizationStateClosed':
                    break

                # 设置TDLib参数
                # 你必须在 https://my.telegram.org 获取自己的api_id和api_hash
                # 并将它们用于setTdlibParameters调用
                if auth_state['@type'] == 'authorizationStateWaitTdlibParameters':
                    td_send({'@type': 'setTdlibParameters',
                             'database_directory': 'tdlib',
                             'use_message_database': True,
                             'use_secret_chats': True,
                             'api_id': 94575,
                             'api_hash': 'a3406de8d171bb422bb6ddf3bbd800e2',
                             'system_language_code': 'en',
                             'device_model': 'Desktop',
                             'application_version': '1.0',
                             'enable_storage_optimizer': True})

                # 输入电话号码进行登录
                if auth_state['@type'] == 'authorizationStateWaitPhoneNumber':
                    phone_number = input('请输入您的电话号码：')
                    td_send({'@type': 'setAuthenticationPhoneNumber', 'phone_number': phone_number})

                # 输入电子邮件地址进行登录
                if auth_state['@type'] == 'authorizationStateWaitEmailAddress':
                    email_address = input('请输入您的电子邮件地址：')
                    td_send({'@type': 'setAuthenticationEmailAddress', 'email_address': email_address})

                # 等待电子邮件授权码
                if auth_state['@type'] == 'authorizationStateWaitEmailCode':
                    code = input('请输入您收到的电子邮件授权码：')
                    td_send({'@type': 'checkAuthenticationEmailCode',
                             'code': {'@type': 'emailAddressAuthenticationCode', 'code': code}})

                # 等待授权码
                if auth_state['@type'] == 'authorizationStateWaitCode':
                    code = input('请输入您收到的授权码：')
                    td_send({'@type': 'checkAuthenticationCode', 'code': code})

                # 如果是新用户，等待名字和姓氏
                if auth_state['@type'] == 'authorizationStateWaitRegistration':
                    first_name = input('请输入您的名字：')
                    last_name = input('请输入您的姓氏：')
                    td_send({'@type': 'registerUser', 'first_name': first_name, 'last_name': last_name})

                # 如果有密码，等待密码输入
                if auth_state['@type'] == 'authorizationStateWaitPassword':
                    password = input('请输入您的密码：')
                    td_send({'@type': 'checkAuthenticationPassword', 'password': password})

            # 处理传入的更新或先前发送请求的答案
            print(str(event))
            type_ = event['@type']
            if ['chat', 'chats', 'messages', 'foundChatMessages', 'updateMessageSendSucceeded'].__contains__(
                    type_):
                QueueUtil.get_instance().producer(type_, event)
            if (event.keys().__contains__('local') and event['local']['@type'].__eq__('localFile')):
                if event['local']['is_downloading_completed']:
                    file_info = QueueUtil.get_instance().consumer(str(event['id']))
                    file_path = event['local']['path']
                    file_caption = file_info['caption']
                    if len(file_caption) > 0:
                        os.rename(file_path, '%s/%s.mp4' % ('/'.join(file_path.split('/')[:-1]), file_caption))
            sys.stdout.flush()


threading.Thread(target=start).start()
