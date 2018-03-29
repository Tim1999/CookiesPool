import json

import requests
import time
from selenium import webdriver
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver import DesiredCapabilities
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from cookiespool.config import *
from cookiespool.db import CookiesRedisClient, AccountRedisClient
from cookiespool.verify import Yundama


class CookiesGenerator(object):
    def __init__(self, name='default', browser_type=DEFAULT_BROWSER):
        """
        父类, 初始化一些对象
        :param name: 名称
        :param browser: 浏览器, 若不使用浏览器则可设置为 None
        """
        self.name = name
        self.cookies_db = CookiesRedisClient(name=self.name)
        self.account_db = AccountRedisClient(name=self.name)
        self.browser_type = browser_type

    def _init_browser(self, browser_type):
        """
        通过browser参数初始化全局浏览器供模拟登录使用
        :param browser: 浏览器 PhantomJS/ Chrome
        :return:
        """
        if browser_type == 'PhantomJS':
            # 获取PhantomJS的配置
            caps = DesiredCapabilities.PHANTOMJS
            caps[
                "phantomjs.page.settings.userAgent"] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36'
            # 创建浏览器对象
            self.browser = webdriver.PhantomJS(desired_capabilities=caps)
            # 设置浏览器窗口大小
            self.browser.set_window_size(1400, 500)
        elif browser_type == 'Chrome':
            # 创建浏览器对象
            self.browser = webdriver.Chrome()

    def new_cookies(self, username, password):
        """
        获取cookies
        :param username: 用户名
        :param password: 密码
        :return: (username,cookies)
        """
        raise NotImplementedError

    def set_cookies(self, account):
        """
        根据账户设置新的Cookies
        :param account:
        :return:
        """
        results = self.new_cookies(account.get('username'), account.get('password'))
        if results:
            username, cookies = results
            print('Saving Cookies to Redis', username, cookies)
            self.cookies_db.set(username, cookies)


    def run(self):
        """
        运行, 得到所有账户, 然后顺次模拟登录
        :return:
        """
        accounts = self.account_db.all()
        cookies = self.cookies_db.all()
        # Account 中对应的用户(生成器转为列表 )
        accounts = list(accounts)
        # Cookies中对应的用户
        valid_users = [cookie.get('username') for cookie in cookies]
        print('Getting', len(accounts), 'accounts from Redis')
        if len(accounts):
            self._init_browser(browser_type=self.browser_type)
        for account in accounts:
            # 判断用户是否已有cookies
            if not account.get('username') in valid_users:
                print('Getting Cookies of ', self.name, account.get('username'), account.get('password'))
                # 获取cookies并保存
                self.set_cookies(account)
        print('Generator Run Finished')

    def close(self):
        """关闭浏览器对象"""
        try:
            print('Closing Browser')
            self.browser.close()
            del self.browser
        except TypeError:
            print('Browser not opened')


class WeiboCookiesGenerator(CookiesGenerator):
    def __init__(self, name='weibo', browser_type=DEFAULT_BROWSER):
        """
        初始化操作, 微博需要声明一个云打码引用
        :param name: 名称微博
        :param browser: 使用的浏览器
        """
        CookiesGenerator.__init__(self, name, browser_type)
        self.name = name
        # 创建一个云打码对象(调用云打码api识别验证码)
        self.ydm = Yundama(YUNDAMA_USERNAME, YUNDAMA_PASSWORD, YUNDAMA_APP_ID, YUNDAMA_APP_KEY)

    def _success(self, username):
        # 创建浏览器等待对象
        wait = WebDriverWait(self.browser, 5)
        # 等待元素加载
        success = wait.until(EC.visibility_of_element_located((By.CLASS_NAME, 'me_portrait_w')))
        if success:
            print('登录成功')
            # 访问网站测试cookies是否可用
            self.browser.get('http://weibo.cn/')

            if "我的首页" in self.browser.title:
                print(self.browser.get_cookies())
                cookies = {}
                # 获取cookies
                for cookie in self.browser.get_cookies():
                    cookies[cookie["name"]] = cookie["value"]
                print(cookies)
                print('成功获取到Cookies')
                return (username, json.dumps(cookies))

    def new_cookies(self, username, password):
        """
        生成Cookies
        :param username: 用户名
        :param password: 密码
        :return: 用户名和Cookies
        """
        print('Generating Cookies of', username)
        # 删除浏览器所有cookeis
        self.browser.delete_all_cookies()
        # 浏览器退出登录
        self.browser.get('http://my.sina.com.cn/profile/unlogin')
        # 创建浏览器等待对象
        wait = WebDriverWait(self.browser, 20)

        try:
            # 等待元素加载
            login = wait.until(EC.visibility_of_element_located((By.ID, 'hd_login')))
            # 点击登录按钮跳转到登录页面
            login.click()
            # 获取用户名输入框并输入用户名
            user = wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, '.loginformlist input[name="loginname"]')))
            user.send_keys(username)
            # 获取密码输入框并输入密码
            psd = wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, '.loginformlist input[name="password"]')))
            psd.send_keys(password)
            # 点击提交按钮
            submit = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.login_btn')))
            submit.click()
            try:
                # 判断是否登录成功，如果报TimeoutException异常说明需要输入验证码
                result = self._success(username)
                if result:
                    return result
            except TimeoutException:
                print('出现验证码，开始识别验证码')
                yzm = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.loginform_yzm .yzm')))
                url = yzm.get_attribute('src')
                # 获取cookies用于获取验证码图片
                cookies = self.browser.get_cookies()
                cookies_dict = {}
                for cookie in cookies:
                    cookies_dict[cookie.get('name')] = cookie.get('value')
                response = requests.get(url, cookies=cookies_dict)
                # 调用云打码api识别验证码
                result = self.ydm.identify(stream=response.content)
                if not result:
                    print('验证码识别失败, 跳过识别')
                    return
                # 获取验证码输入框并输入验证码
                door = wait.until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, '.loginform_yzm input[name="door"]')))
                door.send_keys(result)
                # 再次点击登录
                submit.click()
                # 判断是否登录成功
                result = self._success(username)
                if result:
                    return result
        except WebDriverException as e:
            print(e.args)


class MWeiboCookiesGenerator(CookiesGenerator):
    def __init__(self, name='weibo', browser_type=DEFAULT_BROWSER):
        """
        初始化操作, 微博需要声明一个云打码引用
        :param name: 名称微博
        :param browser: 使用的浏览器
        """
        CookiesGenerator.__init__(self, name, browser_type)
        self.name = name
        self.ydm = Yundama(YUNDAMA_USERNAME, YUNDAMA_PASSWORD, YUNDAMA_APP_ID, YUNDAMA_APP_KEY)

    def _success(self, username):
        wait = WebDriverWait(self.browser, 5)
        success = wait.until(EC.visibility_of_element_located((By.CLASS_NAME, 'me_portrait_w')))

        if success:
            print('登录成功')
            self.browser.get('http://m.weibo.cn/')

            if "微博" in self.browser.title:
                print(self.browser.get_cookies())
                cookies = {}
                for cookie in self.browser.get_cookies():
                    cookies[cookie["name"]] = cookie["value"]
                print(cookies)
                print('成功获取到Cookies')
                return (username, json.dumps(cookies))

    def new_cookies(self, username, password):
        """
        生成Cookies
        :param username: 用户名
        :param password: 密码
        :return: 用户名和Cookies
        """
        print('Generating Cookies of', username)
        self.browser.delete_all_cookies()
        self.browser.get('http://my.sina.com.cn/profile/unlogin')
        wait = WebDriverWait(self.browser, 20)

        try:
            login = wait.until(EC.visibility_of_element_located((By.ID, 'hd_login')))
            login.click()

            user = wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, '.loginformlist input[name="loginname"]')))
            user.send_keys(username)
            psd = wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, '.loginformlist input[name="password"]')))
            psd.send_keys(password)
            submit = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.login_btn')))
            submit.click()
            try:
                result = self._success(username)
                if result:
                    return result
            except TimeoutException:
                print('出现验证码，开始识别验证码')
                yzm = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, '.loginform_yzm .yzm')))
                url = yzm.get_attribute('src')
                cookies = self.browser.get_cookies()

                cookies_dict = {}
                for cookie in cookies:
                    cookies_dict[cookie.get('name')] = cookie.get('value')
                response = requests.get(url, cookies=cookies_dict)
                result = self.ydm.identify(stream=response.content)
                if not result:
                    print('验证码识别失败, 跳过识别')
                    return
                door = wait.until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, '.loginform_yzm input[name="door"]')))
                door.send_keys(result)
                submit.click()
                result = self._success(username)
                if result:
                    return result
        except WebDriverException as e:
            pass


if __name__ == '__main__':
    generator = WeiboCookiesGenerator()
    generator._init_browser('Chrome')
    generator.new_cookies('15197170054', 'gmwkms222')
