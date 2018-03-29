import time
from multiprocessing import Process

from cookiespool.api import app
from cookiespool.config import *
from cookiespool.generator import *
from cookiespool.tester import *

class Scheduler(object):
    @staticmethod
    def valid_cookie(cycle=CYCLE):
        """
        验证cookie的有效性
        :param cycle:验证器循环周期(秒)
        :return:
        """
        while True:
            print('Checking Cookies')
            try:
                # 获取所以站点和站点的测试类
                for name, cls in TESTER_MAP.items():
                    # 创建测试对象
                    tester = eval(cls + '(name="' + name + '")')
                    # 启动测试对象
                    tester.run()
                    print('Tester Finished')
                    del tester
                    # 休眠一个循环周期
                    time.sleep(cycle)
            except Exception as e:
                print(e.args)

    @staticmethod
    def generate_cookie(cycle=CYCLE):
        """
        获取登录后的cookie
        :param cycle: 产生器的循环周期
        :return:
        """
        while True:
            print('Generating Cookies')
            try:
                # 获取所有站点和站点产生器类
                for name, cls in GENERATOR_MAP.items():
                    # 创建产生器对象
                    generator = eval(cls + '(name="' + name + '")')
                    # 运行产生器
                    generator.run()
                    print('Generator Finished')
                    # 关闭产生器（关闭selnium浏览器对象）
                    generator.close()
                    print('Deleted Generator')
                    # 休眠一个循环周期
                    time.sleep(cycle)
            except Exception as e:
                print(e.args)

    @staticmethod
    def api():
        """启动api接口"""
        app.run(host=API_HOST, port=API_PORT)

    def run(self):
        """根据配置文件启动所用程序"""
        if GENERATOR_PROCESS:
            generate_process = Process(target=Scheduler.generate_cookie)
            generate_process.start()

        if VALID_PROCESS:
            valid_process = Process(target=Scheduler.valid_cookie)
            valid_process.start()

        if API_PROCESS:
            api_process = Process(target=Scheduler.api)
            api_process.start()

