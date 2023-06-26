# -*- coding: utf-8 -*-
"""
Created on Wed Mar 29 11:39:36 2023

@author: jellyho
"""

import socket
import signal
import sys
import time
import select
from PyQt5.QtGui import QFont, QImage, QPixmap
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5 import uic
import threading


form_class = uic.loadUiType("RCServerUI.ui")[0]

class Information:
    def __init__(self, A, B):
        self.A = A
        self.B = B



class ServerWorker(QObject):
    update = pyqtSignal(Information)
    
    def __init__(self, port=2023, protocol='tcp'):
        super().__init__()
        self.sock = None
        self.port = port
        self.bufferSize = 1024
        self.protocol = protocol
        self.tcp_buffer_A = 0
        self.tcp_beffer_B = 0
        self.A = [('0','0'), False, 0.0, None, 0.0, 'STOP'] # ip , connected , battery, socket, ping
        self.B = [('0','0'), False, 0.0, None, 0.0, 'STOP']
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        host = socket.gethostname()
        self.host_ip = socket.gethostbyname(host)
        print(f'TCP Server Opened : {self.host_ip}:{self.port}')
        self.sock.bind((self.host_ip, self.port))
        self.sock.listen()
    
    @pyqtSlot()
    def Run(self):
        while True:
            print('Waiting for Connection...')  #Aceeption Stage
            while not (self.A[1] and self.B[1]):
                client_socket, addr = self.sock.accept()
                print(f'Connection Ocurred {addr}')
                client_socket.send('H'.encode()) #handshake
                while True:
                    data = client_socket.recv(1024)
                    message = data.decode()
                    print(message);
                    client_socket.settimeout(3)
                    if message == 'A':
                        self.A = [addr, True, 1.0, client_socket, 0.0, 'STOP']
                        self.carA_ip = addr
                        print('Car A Connected', addr)
                        break
                    elif message == 'B':
                        self.B = [addr, True, 1.0, client_socket, 0.0, 'STOP']
                        self.carB_ip = addr
                        print('Car B Connected', addr)
                        break
                self.update.emit(Information(self.A, self.B))
                
            while True: #Connection Check Stage
                print("Checking")
                if self.A[1]:
                    start_time = time.time()
                    self.A[3].send('C'.encode())
                    try:
                        data = self.A[3].recv(1024).decode()
                        data = data.split('-')
                        self.A[2] = float(data[1])
                    except socket.timeout:
                        print("Connection Lost A")
                        self.A[3].close()
                        self.A = [('0','0'), False, 0.0, None, 0.0, 'STOP']
                        self.update.emit(Information(self.A, self.B))
                        break
                    end_time = time.time()
                    elapsed_time = end_time - start_time
                    self.A[4] = elapsed_time  
                if self.B[1]:
                    start_time = time.time()
                    self.B[3].send('C'.encode())
                    try:
                        data = self.B[3].recv(1024)
                        data = data.decode()
                        data = data.split('-')
                        self.B[2] = float(data[1])
                    except socket.timeout:
                        print("Connection Lost B")
                        self.B[3].close()
                        self.B = [('0','0'), False, 0.0, None, 0.0, 'STOP']
                        self.update.emit(Information(self.A, self.B))
                        break
                    end_time = time.time()
                    elapsed_time = end_time - start_time
                    self.B[4] = elapsed_time
                self.update.emit(Information(self.A, self.B))
                time.sleep(1)
            
    @pyqtSlot()
    def Stop(self):
        print("Server Stop")
        self.Close = True
        time.sleep(1)
        self.sock.close()
        
    
    def Act(self, robot='A', act='STOP', v=1):
        speed = (0, 0)
        data = (0, 0)
        if act == 'W':
            speed = (v, v)
        elif act == 'S':
            speed = (-v, -v)
        elif act == 'A':
            speed = (-v, v)
        elif act == 'D':
            speed = (v, -v)
        else:
            pass
        actions = {'W': 'Foward', 'S': 'Backward', 'A': 'Left', 'D': 'Right', 'STOP': 'STOP'}
        message = f'A{int(speed[0]*255)}&{int(speed[1]*255)}'
        message = message.encode()
        
        if self.protocol =='tcp':
            if robot == 'A':
                self.A[3].send(message)
                self.A[5] = actions[act]
            elif robot =='B':
                self.B[3].send(message)
                self.B[5] = actions[act]
        self.update.emit(Information(self.A, self.B))

class RCServer(QMainWindow, form_class):
    AcceptStart = pyqtSignal()
    ServerEnd = pyqtSignal()
    MainStart = pyqtSignal()
    
    def __init__(self, carA_ip='192.168.0.201', carB_ip='192.168.0.13', port=2023, protocol='tcp'):
        super().__init__()
        self.setWindowTitle('Dreams Come True')
        self.setupUi(self)
        self.Manual = None
        # Qt
        
        self.worker = ServerWorker(port=port, protocol=protocol)
        # Server
        
        # Server Start
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.start()
        
        self.worker.update.connect(self.update)
        self.AcceptStart.connect(self.worker.Run)
        self.ServerEnd.connect(self.worker.Stop)
        self.AcceptStart.emit()
        
        self.Manual_A.released.connect(self.manualModeA)
        self.Manual_B.released.connect(self.manualModeB)
    
    def setMain(self, main):
        self.mainworker = main
        self.mainthread = QThread()
        self.mainworker.moveToThread(self.mainthread)
        self.mainthread.start()
        
        self.MainStart.connect(self.mainworker.main)
        self.MainStart.emit()
        
    def updateStatus(self, frame, status):
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        image = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(image)
        self.pixMap.setPixmap(pixmap)
        self.status.setText(status)
        
    def keyPressEvent(self, e):
        if self.Manual is not None:
            if e.key() == Qt.Key_W:
                self.worker.Act(self.Manual, 'W')
            elif e.key() == Qt.Key_S:
                self.worker.Act(self.Manual, 'S')
            elif e.key() == Qt.Key_D:
                self.worker.Act(self.Manual, 'D')
            elif e.key() == Qt.Key_A:
                self.worker.Act(self.Manual, 'A')
            else:
                self.worker.Act(self.Manual, 'STOP')
    
    def manualModeA(self):
        if self.Manual == 'A':
            self.Manual_A.toggle()
            self.Manual = None
            self.Manual_Status.setText('No Manual Drive')
        else:
            self.Manual = 'A'
            self.Manual_A.toggle()
            self.Manual_Status.setText('A')
    
    def manualModeB(self):
        if self.Manual == 'B':
            self.Manual = None
            self.Manual_Status.setText('No Manual Drive')
        else:
            self.Manual = 'B'
            self.Manual_Status.setText('B')
            
    def available(self):
        return self.worker.A[1] and self.worker.B[1]
        
    
    @pyqtSlot(Information)     
    def update(self, info):
        A, B = info.A, info.B
        if A[1]:
            self.Connection_A.setText(f'{A[0][0]}:{A[0][1]}')
            self.Battery_A.setValue(int(A[2] * 100))
            self.Ping_A.setText(f'{A[4]*1000:.1f}ms')
            self.Current_Action_A.setText(A[5])
        else:
            self.Connection_A.setText(f'Disconnected')
        if B[1]:
            self.Connection_B.setText(f'{B[0][0]}:{B[0][1]}')
            self.Battery_B.setValue(int(B[2] * 100))
            self.Ping_B.setText(f'{B[4]*1000:.1f}ms')
            self.Curernt_Action_B.setText(B[5])
        else:
            self.Connection_B.setText(f'Disconnected')
        
    def closeEvent(self, event):
        quit_msg = "Want to exit?"
        reply = QMessageBox.question(self, 'Message', quit_msg, QMessageBox.Yes, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.ServerEnd.emit()
            self.worker.sock.close()
            time.sleep(2)
            self.thread.terminate()
            self.mainthread.terminate()
            event.accept()
        else:
            event.ignore()