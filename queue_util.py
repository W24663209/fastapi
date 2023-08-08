import threading
import time
from queue import Queue


class QueueUtil:
    # 定义类变量用于存储单例对象
    _instance = None

    # 定义类方法获取单例对象
    @classmethod
    def get_instance(cls):
        if not cls._instance:
            cls._instance = QueueUtil()
        return cls._instance

    def __init__(self):
        self.queue = Queue()

    # 生产者函数
    def producer(self, key, items):
        try:
            print(f'生产者({key})生产了: {items}')
            self.queue.put((key, items))  # 发送一个结束信号，表示生产结束
        except:
            pass

    # 消费者函数
    def consumer(self, key):
        try:
            while True:
                item = self.queue.get(timeout=5)
                if item[1]['@type'] == key:
                    return item[1]
        except:
            pass


if __name__ == '__main__':
    # 创建一个队列对象
    util = QueueUtil()

    # 创建并启动生产者线程
    items1 = ['item1', 'item2', 'item3']
    producer_thread1 = threading.Thread(target=util.producer, args=('key1', items1))
    producer_thread1.start()

    items2 = ['item4', 'item5', 'item6']
    producer_thread2 = threading.Thread(target=util.producer, args=('key2', items2))
    producer_thread2.start()

    # 创建并启动消费者线程
    consumer_thread1 = threading.Thread(target=util.consumer, args=('key1',))
    consumer_thread1.start()

    consumer_thread2 = threading.Thread(target=util.consumer, args=('key2',))
    consumer_thread2.start()

    # 等待生产者线程和消费者线程结束
    producer_thread1.join()
    producer_thread2.join()
    consumer_thread1.join()
    consumer_thread2.join()

    print('生产消费模式结束')
