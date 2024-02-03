# -*- coding: gbk -*-

import sys
import time
from PyQt5.QtWidgets import QApplication, QMainWindow
from tool_ui import Ui_Form
import serial.tools.list_ports
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QTimer, Qt
import serial
import os
import subprocess
import struct
import json
import configparser

TERM_BUFSIZE = 1000  # 终端缓冲区大小
SERIAL_PORT_TIMEOUT_MS = 200  # 串口超时时间,单位ms

main_window = None


class DataStory:

    config: configparser.ConfigParser = None

    def __init__(self):
        self.config = configparser.ConfigParser()

    def Save(self, key, value):
        try:
            self.config.set('Section1', key, value)
            with open('config.ini', 'w') as configfile:
                self.config.write(configfile)
        except Exception as e:
            print(f"Error saving configuration: {e}")

    def Load(self):
        self.config.read('config.ini')

    def Get(self, key):
        try:
            return self.config.get('Section1', key)
        except Exception as e:
            print(f"Error retrieving configuration: {e}")
            return None


class Paramer:

    def __init__(self):
        pass

    port = None  # 串口对象
    ser: serial.Serial = None  # 串口对象
    ui: Ui_Form = None

    def Connect(self):
        text = self.ui.conn_pushButton.text()
        self.port = ui.select_com_comboBox.currentText()
        if (text == "打开"):
            try:
                self.ser = serial.Serial(self.port, 115200, timeout=SERIAL_PORT_TIMEOUT_MS / 1000)
                if (self.ser != None):  # serial port open succeed
                    self.ui.conn_pushButton.setText("关闭")
            except serial.SerialException as e:
                print(f"Could not open serial port: {e}")
                raise e

        elif (text == "关闭"):
            if (self.ser != None):
                self.ser.close()  # close serial port
                self.ui.conn_pushButton.setText("打开")
                self.ser = None

    def SetUI(self, ui: Ui_Form):
        self.ui = ui

    def SendMsg():  # 与下位机通讯,发送消息
        pass

    def ModbusCrc16_LSB(self, data: bytes, poly=0xA001):  # 计算CRC校验码
        '''modbus-crc16 Algorithm(LSB)'''
        reg = 0xFFFF
        for byte in data:
            reg ^= byte
            for _ in range(8):
                if reg & 0x0001:
                    reg >>= 1
                    reg ^= poly
                else:
                    reg >>= 1
        # data[0],reg[1] = reg[1], data[0]
        # tmp = reg.to_bytes(2, byteorder='little')
        reg1 = reg >> 8
        reg2 = reg & 0xFF
        reg = reg2 << 8 | reg1
        return reg

    # 构建modbus03报文,读取多个寄存器
    # 字段名称	    长度（字节）	描述
    # 设备地址	    1	           用于标识 Modbus 网络中的设备。
    # 功能码	    1	           用于标识请求的类型。在这个情况下，功能码为 3，表示读取多个保持寄存器。
    # 起始地址	    2	           要读取的第一个保持寄存器的地址。
    # 寄存器数量	2	           要读取的保持寄存器的数量。
    # 错误检查（CRC）2	           用于检查报文是否在传输过程中被修改。
    def BuildModbus03Msg(self, addr: int, fcode: int, start_reg_addr: int, reg_cnt: int):

        # 将设备地址、功能码、起始地址和寄存器数量打包为一个字节串
        # >：这个字符表示数据的字节顺序是大端模式。在大端模式中，多字节值的最高位字节在最前面。
        # B：这个字符表示一个无符号字符，它的长度是1字节。
        # H：这个字符表示一个无符号短整型，它的长度是2字节。
        message: bytes = struct.pack('>B B H H', addr, fcode, start_reg_addr, reg_cnt)
        crc = self.ModbusCrc16_LSB(message)  # 计算 CRC 校验码
        message += struct.pack('<H', crc)  # 将 CRC 校验码添加到报文的末尾
        return message

    # 构建modbus16报文,写多个个寄存器
    # 字段名称	    长度（字节）	描述
    # 设备地址	    1	           用于标识 Modbus 网络中的设备。
    # 功能码	    1	           用于标识请求的类型。在这个情况下，功能码为 16，表示写入多个保持寄存器。
    # 起始地址	    2	           要写入的第一个保持寄存器的地址。
    # 寄存器数量	2	           要写入的保持寄存器的数量。
    # 字节计数	    1	           表示接下来的寄存器值字段的字节长度。
    # 寄存器值	    n	           包含了要写入的所有寄存器的值，每个寄存器的值占用 2 字节。
    # 错误检查（CRC）2	           用于检查报文是否在传输过程中被修改。
    def BuildModbus16Msg(self, addr: int, fcode: int, reg_addr: int, reg_cnt: int, reg_data: bytes):

        # 将设备地址、功能码、起始地址和寄存器数量打包为一个字节串
        # >：这个字符表示数据的字节顺序是大端模式。在大端模式中，多字节值的最高位字节在最前面。
        # B：这个字符表示一个无符号字符，它的长度是1字节。
        # H：这个字符表示一个无符号短整型，它的长度是2字节。
        message: bytes = struct.pack('>B B H H H', addr, fcode, reg_addr, reg_cnt, reg_cnt * 2)
        message += reg_data
        for i in range(1000 - len(reg_data)):  # 填充0,保证报文数据域长度为1000
            message += b'\x00'
        crc = self.ModbusCrc16_LSB(message)  # 计算 CRC 校验码
        message += struct.pack('<H', crc)  # 将 CRC 校验码添加到报文的末尾
        return message

    # jdoc["soft_version"] = soft_version;
    # String mac_addr = WiFi.macAddress();
    # mac_addr.replace(":", "");
    # jdoc["drive_no"] = mac_addr.c_str();
    # jdoc["client_id"] = mac_addr.c_str();
    # jdoc["ssid"] = "88888888";
    # jdoc["password"] = "88888888";
    # jdoc["mqtt_server"] = "hcdda1ed.ala.cn-hangzhou.emqxsl.cn";
    # jdoc["mqtt_port"] = 8883;
    # jdoc["mqtt_username"] = "dl2binary";
    # jdoc["mqtt_password"] = "wocaonima88jqk";
    # jdoc["group_ctrl_topic"] = "group_control";
    # jdoc["group_stat_topic"] = "group_status";
    # jdoc["pub_ctrl_topic"] = "public_control";
    # jdoc["pub_stat_topic"] = "public_status";
    # jdoc["ctrl_topic"] = jdoc["drive_no"].as<String>() + "/" + "contrl";
    # jdoc["stat_topic"] = jdoc["drive_no"].as<String>() + "/" + "status";
    # jdoc["modify_config_topic"] = "config_modify";
    # jdoc["read_config_topic"] = "read_config";
    def ReadAll_cb(self):
        if (self.ser == None):
            ui_tool.Tip("请先打开串口")
            return
        msg: bytes = self.BuildModbus03Msg(1, 3, 0, TERM_BUFSIZE // 2)
        self.ser.write(msg)
        time.sleep(SERIAL_PORT_TIMEOUT_MS / 1000)  # wait for responsed to received buffer
        response_data: bytes = self.ser.read(TERM_BUFSIZE)
        reg_data: bytes = response_data[4:-2]  # 解析寄存器值
        # reg_data = reg_data.decode("gbk")
        # idx = 0
        json_data = str()
        for b in reg_data:
            if (b > 33 and b < 127):  # 33-127是可见字符
                json_data += chr(b)
                if (chr(b) == '}'):  # 确保json数据正确
                    break
        try:
            json_data = json.loads(json_data)
        except Exception as e:
            print(f"Error parsing json data: {e}")
            ui_tool.Tip("读取失败")
            return
        ui.softver_lineEdit.setText(json_data["soft_version"])
        ui.drive_no_lineEdit.setText(json_data["drive_no"])
        ui.group_ctrl_topic_lineEdit.setText(json_data["group_ctrl_topic"])
        ui.group_stat_topic_lineEdit.setText(json_data["group_stat_topic"])
        ui.server_ip_lineEdit.setText(json_data["mqtt_server"])
        ui.server_port_lineEdit.setText(str(json_data["mqtt_port"]))
        ui.wifi_ssid_lineEdit.setText(json_data["ssid"])
        ui.wifi_password_lineEdit.setText(json_data["password"])
        ui.mqtt_username_lineEdit.setText(json_data["mqtt_username"])
        ui.mqtt_password_lineEdit.setText(json_data["mqtt_password"])

    def WriteAll_cb(self):  # 写入所有配置,读取lineEdit的内容,写入到下位机
        if (self.ser == None):
            ui_tool.Tip("请先打开串口")
            return
        # 1. 读取lineEdit的内容
        # 2. 构建出json数据作为寄存器值
        # 3. 构建modbus16报文
        # 4. 发送报文
        # 5. 接收返回报文
        # 6. 解析返回报文,正确接收到报文,则提示用户写入成功(弹窗提示)

        jstr = {}
        jstr["soft_version"] = ui.softver_lineEdit.text()
        jstr["drive_no"] = ui.drive_no_lineEdit.text()
        jstr["group_ctrl_topic"] = ui.group_ctrl_topic_lineEdit.text()
        jstr["group_stat_topic"] = ui.group_stat_topic_lineEdit.text()
        jstr["mqtt_server"] = ui.server_ip_lineEdit.text()
        jstr["mqtt_port"] = int(ui.server_port_lineEdit.text())
        jstr["ssid"] = ui.wifi_ssid_lineEdit.text()
        jstr["password"] = ui.wifi_password_lineEdit.text()
        jstr["mqtt_username"] = ui.mqtt_username_lineEdit.text()
        jstr["mqtt_password"] = ui.mqtt_password_lineEdit.text()

        jstr = json.dumps(jstr)
        jbytes = jstr.encode("gbk")

        msg: bytes = paramer.BuildModbus16Msg(1, 16, 0, TERM_BUFSIZE // 2, jbytes)
        # for b in msg:
        #     print("%02x" % b, end=" ")
        # print(msg)
        self.ser.write(msg)
        time.sleep(SERIAL_PORT_TIMEOUT_MS / 1000)  # wait for responsed to received buffer
        response_data: bytes = self.ser.read(8)
        recv_crc = response_data[-2:]
        calc_crc = self.ModbusCrc16_LSB(response_data[:-2])
        if (int.from_bytes(recv_crc) == calc_crc):
            ui_tool.Tip("写入成功")
        else:
            ui_tool.Tip("写入失败")


class Downloader:

    # filepath = None
    # com = "COM11"
    # curdir = os.getcwd()
    # platformio_exe_path = os.path.join(curdir, "platformio.exe")
    # parent_dir = os.path.dirname(curdir)
    # project_dir = os.path.join(parent_dir, "wifi_circuit_breaker")

    # def run_command(self, cmd):
    #     try:
    #         output = subprocess.check_output(cmd, shell=True)
    #         return output
    #     except subprocess.CalledProcessError as e:
    #         print(f"Error: {e}")
    #     return None

    def Download_cb(self):  # 下载固件, 传递给命令行 download_cmd 命令,调用 platformio.exe 下载固件
        filepath = ui.filepath_lineEdit.text().replace("\\", "/")
        data_story.Save('filepath', filepath)
        com = ui.select_com_comboBox.currentText()  # 获取当前选中的串口
        download_cmd = "python.exe esptool.py --port %s write_flash 0x00000 %s" % (com, filepath)
        os.system(download_cmd)
        ui_tool.Tip("下载成功")


class UI_Tool:

    class AutoClosingMessageBox(QMessageBox):  # 自动关闭的提示框

        def __init__(self, timeout=2000, parent=None):
            super().__init__(parent)
            self.timeout = timeout

            self.timer = QTimer(self)
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self.close)
            self.timer.start(self.timeout)

        def showEvent(self, event):  # 在该显示组件被创建时,自动调用
            self.timer.start(self.timeout)
            super().showEvent(event)

        # def exec_(self):
        #     self.addButton(QMessageBox.NoButton)  # Remove the "OK" button
        #

    ui: Ui_Form = None

    def __init__(self):
        pass

    def SetUi(self, ui: Ui_Form):
        self.ui = ui

    def Tip(self, message, duration=2000):
        # 创建一个AutoClosingMessageBox实例
        msgBox = self.AutoClosingMessageBox(duration, main_window)
        msgBox.setText(message)
        msgBox.setWindowModality(Qt.NonModal)
        msgBox.show()

    def DIP_Setting(self):
        if hasattr(Qt, 'AA_EnableHighDpiScaling'):
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)

        if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
            QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


def QueryComs():
    '''查询可用串口,返回一个列表，包含所有可用串口的名称'''
    coms = serial.tools.list_ports.comports()
    comlist = []
    for com in coms:
        comlist.append(com.device)
    return comlist


paramer = Paramer()
downloader = Downloader()
ui_tool = UI_Tool()
data_story = DataStory()

data_story.Load()

ui_tool.DIP_Setting()  # 保证高分屏下界面显示正常

app = QApplication(sys.argv)
main_window = QMainWindow()
ui = Ui_Form()
ui.setupUi(main_window)
main_window.show()

coms = QueryComs()
ui.select_com_comboBox.addItems(coms)

if (data_story.Get("filepath") != None):
    ui.filepath_lineEdit.setText(data_story.Get("filepath"))

ui.download_pushButton.clicked.connect(downloader.Download_cb)
ui.conn_pushButton.clicked.connect(paramer.Connect)
ui.queryall_pushButton.clicked.connect(paramer.ReadAll_cb)
ui.updataall_pushButton.clicked.connect(paramer.WriteAll_cb)

paramer.SetUI(ui)
ui_tool.SetUi(ui)
# filepath_lineEdit 的内容保存到 filepath 中
# ui.filepath_lineEdit.setText(project_dir)
# ui.filepath_lineEdit.setPlaceholderText(project_dir)
# filepath = ui.filepath_lineEdit.text()

sys.exit(app.exec_())
