import json
import time

from util.route import route
from util.log import logger
import tornado.web
import os
import requests
import traceback

dd_token = 'a3107af12595f8d0c0652a4b38b3a032c485e1699b089bebe272e82d949aa3d2'

# Set up the model and prompt
model_engine = "gpt-3.5-turbo"

retry_times = 10

global_dict = {}


@route("/")
class ChatgptHandler(tornado.web.RequestHandler):

    def get(self):
        return self.write_json({"ret": 200})

    def post(self):
        try:
            request_data = self.request.body
            data = json.loads(request_data)
            prompt = data['text']['content']

            if "/syncImage" in prompt:
                content = " ".join(prompt.split(" ")[1:])
                response = json.loads(self.submit(content).text)
                logger.info(f"parse response: {response}")
                # 存储用户-请求对应的数据
                self.set_context(data, response)
                self.notify_dingding(f"任务id:{response['result']},已完成0%，请等待")
                taskid = response['result']
                i = 0
                while i < retry_times:
                    time.sleep(20)
                    resp = json.loads(self.check(taskid).text)
                    status = resp['status']
                    imgurl = resp['imageUrl']
                    progress = resp['progress']

                    if status == "FAILED":
                        self.notify_dingding(f"任务id:{taskid}g了，原因未知")
                        break
                    elif progress != '100%':
                        i += 1
                        self.notify_dingding(f"任务id:{taskid},已完成{progress}，请等待")
                    else:
                        localurl = self.download_save_image(imgurl)
                        self.notify_dingding(f"任务id:{taskid},图片链接：{localurl}")
                        break


            if "/image" in prompt:
                content = prompt.split(" ")[1:]
                response = json.loads(self.submit(content).text)

                logger.info(f"parse response: {response}")
                # 存储用户-请求对应的数据
                self.set_context(data, response)
                self.notify_dingding(f"任务id:{response['result']},已完成0%，请等待")

            if "/check" in prompt:
                ctx = self.get_context(data)
                taskid = ctx[-1]['content']['result']
                resp = json.loads(self.check(taskid).text)
                status = resp['status']
                imgurl = resp['imageUrl']
                progress = resp['progress']

                if status == "FAILED":
                    self.notify_dingding(f"任务id:{taskid}g了，原因未知")
                elif progress != '100%':
                    self.notify_dingding(f"任务id:{taskid},已完成{progress}，请等待")
                else:
                    localurl = self.download_save_image(imgurl)
                    self.notify_dingding(f"任务id:{taskid},图片链接：{localurl}")

            return self.write_json({"ret": 200})
        except:
            traceback.print_exc()
            return self.write_json({"ret": 500})

    def submit(self, prompt):
        # 调用 imagine 函数并传递参数
        params = {
            'base64Array': [],
            'notifyHook': '',
            'prompt': prompt,
            'state': ''
        }
        url = 'https://midjproxyt.zeabur.app/mj/submit/imagine'
        response = requests.post(url, json=params)
        return response

    def check(self, id):
        url = f'https://midjproxyt.zeabur.app/mj/task/{id}/fetch'
        response = requests.get(url)
        return response

    def download_save_image(self, url):
        # 发送GET请求获取图片数据
        response = requests.get(url)
        name = url.split("/")[-1]
        # 检查响应状态码是否成功
        if response.status_code == 200:
            # 打开文件并写入图片数据
            path = os.path.join("../images", name)
            if os.path.exists(path):
                return "listener.zeabur.app/images/" + name
            with open(path, 'wb') as file:
                file.write(response.content)
            logger.info(f"图片已成功下载并保存为: {name}")
        else:
            logger.info("图片下载失败")
        return "listener.zeabur.app/images/" + name

    def get_context(self, data):
        storeKey = self.get_context_key(data)
        if (global_dict.get(storeKey) is None):
            global_dict[storeKey] = []
        return global_dict[storeKey]

    def get_context_key(self, data):
        conversation_id = data['conversationId']
        sender_id = data['senderId']
        return conversation_id + '@' + sender_id

    def set_context(self, data, response):
        prompt = data['text']['content']
        storeKey = self.get_context_key(data)
        if (global_dict.get(storeKey) is None):
            global_dict[storeKey] = []
        global_dict[storeKey].append({"role": "user", "content": prompt})
        global_dict[storeKey].append(
            {"role": "assistant", "content": response})

    def clear_context(self, data):
        store_key = self.get_context_key(data)
        global_dict[store_key] = []

    def write_json(self, struct):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        self.write(tornado.escape.json_encode(struct))

    def notify_dingding(self, answer):
        answer = "/image " + answer
        data = {
            "msgtype": "text",
            "text": {
                "content": answer
            },

            "at": {
                "atMobiles": [
                    ""
                ],
                "isAtAll": False
            }
        }

        notify_url = f"https://oapi.dingtalk.com/robot/send?access_token={dd_token}"
        try:
            r = requests.post(notify_url, json=data)
            reply = r.json()
            logger.info("dingding: " + str(reply))
        except Exception as e:
            logger.error(e)
