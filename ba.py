from rpc import start_rpc_server
start_rpc_server(port=1133, key='', globals_dict=globals())
import sys, os, threading
from kivy.config import Config
from kivy.utils import platform

if platform == 'android':
    from jnius import autoclass, PythonJavaClass, java_method
    from android.permissions import request_permissions, Permission
    from android import activity
    BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
    BluetoothDevice = autoclass('android.bluetooth.BluetoothDevice')
    IntentFilter = autoclass('android.content.IntentFilter')
    BroadcastReceiver = autoclass('android.content.BroadcastReceiver')
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Config.set('kivy', 'default_font', ['Roboto', 'DroidSansFallback.ttf'])  # Android 默认字体
else:
    BluetoothAdapter = None
    Config.set('kivy', 'default_font', ['C:/Windows/Fonts/msyh.ttc'] * 4)
    # 模拟 PythonJavaClass
    class PythonJavaClass:
        def __init__(self):
            pass
    def java_method(*args, **kwargs):
        def decorator(func):
            func.__javamethod__ = True
            return func
        return decorator


Config.write()
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock, mainthread

class BluetoothReceiver(PythonJavaClass):
    __javainterfaces__ = ['android/content/BroadcastReceiver']
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
    @java_method('(Landroid/content/Context;Landroid/content/Intent;)V')
    def onReceive(self, context, intent):
        action = intent.getAction()
        if action == BluetoothDevice.ACTION_FOUND:
            device = intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
            self.callback(device)
        elif action == BluetoothDevice.ACTION_BOND_STATE_CHANGED:
            device = intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
            state = intent.getIntExtra(BluetoothDevice.EXTRA_BOND_STATE, -1)
            self.callback(None, bond_device=device, bond_state=state)

class BluetoothScanner(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        top_bar = BoxLayout(orientation='horizontal', size_hint_y=0.1)
        self.scan_btn = Button(text='开始扫描', size_hint_x=0.3)
        self.scan_btn.bind(on_press=self.start_scan)
        self.exit_btn = Button(text='退出', size_hint_x=0.2)
        self.exit_btn.bind(on_press=lambda x: sys.exit(0))
        top_bar.add_widget(self.scan_btn)
        top_bar.add_widget(self.exit_btn)
        top_bar.add_widget(Label(text='蓝牙设备列表', size_hint_x=0.5))
        self.add_widget(top_bar)
        self.device_list = BoxLayout(orientation='vertical', size_hint_y=None)
        self.device_list.bind(minimum_height=self.device_list.setter('height'))
        scroll = ScrollView()
        scroll.add_widget(self.device_list)
        self.add_widget(scroll)
        self.devices = {}
        self.receiver = None
        self.bluetooth_adapter = None
        if platform == 'android':
            request_permissions([Permission.BLUETOOTH_SCAN, Permission.BLUETOOTH_CONNECT,
                                 Permission.ACCESS_FINE_LOCATION, Permission.BLUETOOTH,
                                 Permission.BLUETOOTH_ADMIN])
            Clock.schedule_once(self.init_bluetooth, 1)
    def init_bluetooth(self, dt):
        self.bluetooth_adapter = BluetoothAdapter.getDefaultAdapter()
        if self.bluetooth_adapter is None:
            self.add_widget(Label(text='设备不支持蓝牙', color=(1,0,0,1)))
            return
        if not self.bluetooth_adapter.isEnabled():
            activity.startActivityForResult(Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE), 1)
    def start_scan(self, instance):
        if not self.bluetooth_adapter:
            return
        self.clear_devices()
        self.receiver = BluetoothReceiver(self.on_device_found)
        filter = IntentFilter(BluetoothDevice.ACTION_FOUND)
        filter.addAction(BluetoothDevice.ACTION_BOND_STATE_CHANGED)
        PythonActivity.mActivity.registerReceiver(self.receiver, filter)
        self.bluetooth_adapter.startDiscovery()
        self.scan_btn.text = '扫描中...'
        self.scan_btn.disabled = True
        Clock.schedule_once(self.stop_scan, 12)
    def stop_scan(self, dt):
        if self.bluetooth_adapter.isDiscovering():
            self.bluetooth_adapter.cancelDiscovery()
        if self.receiver:
            PythonActivity.mActivity.unregisterReceiver(self.receiver)
            self.receiver = None
        self.scan_btn.text = '开始扫描'
        self.scan_btn.disabled = False
    def clear_devices(self):
        self.device_list.clear_widgets()
        self.devices.clear()
    @mainthread
    def on_device_found(self, device, bond_device=None, bond_state=None):
        if device:
            name = device.getName() or '未知设备'
            address = device.getAddress()
            if address not in self.devices:
                btn = Button(text=f'{name}\n{address}', size_hint_y=None, height=60)
                btn.bind(on_press=lambda x: self.connect_device(device))
                self.device_list.add_widget(btn)
                self.devices[address] = btn
        elif bond_device:
            address = bond_device.getAddress()
            if address in self.devices:
                state_str = {10:'未配对', 11:'配对中', 12:'已配对'}.get(bond_state, '未知')
                self.devices[address].text = f'{bond_device.getName()}\n{address} [{state_str}]'
    def connect_device(self, device):
        if device.getBondState() == BluetoothDevice.BOND_NONE:
            device.createBond()
            self.scan_btn.text = '正在配对...'
        else:
            threading.Thread(target=self._do_connect, args=(device,), daemon=True).start()
    def _do_connect(self, device):
        from jnius import autoclass
        UUID = autoclass('java.util.UUID')
        MY_UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
        try:
            socket = device.createRfcommSocketToServiceRecord(MY_UUID)
            socket.connect()
            Clock.schedule_once(lambda dt: self.add_widget(Label(text=f'已连接到 {device.getName()}', color=(0,1,0,1))))
        except Exception as e:
            Clock.schedule_once(lambda dt: self.add_widget(Label(text=f'连接失败: {e}', color=(1,0,0,1))))

class BluetoothApp(App):
    def build(self):
        return BluetoothScanner()

if __name__ == '__main__':
    BluetoothApp().run()