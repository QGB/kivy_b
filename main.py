from rpc import start_rpc_server
start_rpc_server(port=1133, key='', globals=globals(), locals=locals())

import sys, threading, traceback, time
from kivy.config import Config
from kivy.utils import platform

if platform != 'android':
    Config.set('kivy', 'default_font', ['C:/Windows/Fonts/msyh.ttc'] * 4)
    Config.write()

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock, mainthread
from kivy.core.clipboard import Clipboard

class DeviceItem(BoxLayout):
    def __init__(self, name, address, callback, **kwargs):
        super().__init__(orientation='horizontal', size_hint_y=None, height=50, **kwargs)
        self.callback = callback
        self.device_address = address
        self.name_label = Label(text=name, size_hint_x=0.6, halign='left', valign='middle')
        self.name_label.bind(size=self.name_label.setter('text_size'))
        self.addr_label = Label(text=address, size_hint_x=0.4, halign='right', valign='middle')
        self.addr_label.bind(size=self.addr_label.setter('text_size'))
        self.add_widget(self.name_label)
        self.add_widget(self.addr_label)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.callback(self.device_address)
            return True
        return super().on_touch_down(touch)

class BluetoothScanner(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        top_bar = BoxLayout(orientation='horizontal', size_hint_y=0.1)
        self.scan_btn = Button(text='SCAN', size_hint_x=0.3)
        self.scan_btn.bind(on_press=self.start_scan)
        self.exit_btn = Button(text='EXIT', size_hint_x=0.2)
        self.exit_btn.bind(on_press=lambda x: sys.exit(0))
        top_bar.add_widget(self.scan_btn)
        top_bar.add_widget(self.exit_btn)
        top_bar.add_widget(Label(text='BLUETOOTH LIST', size_hint_x=0.5))
        self.add_widget(top_bar)

        self.msg_text = TextInput(text='', readonly=True, multiline=True,
                                  size_hint_y=0.6,
                                  background_color=(0.1,0.1,0.1,1),
                                  foreground_color=(0,1,0,1),
                                  halign='left')
        self.msg_text.bind(size=self._update_text_size)
        self.msg_text.bind(on_touch_up=self._on_msg_touch)
        self.add_widget(self.msg_text)

        self.device_container = BoxLayout(orientation='vertical', size_hint_y=None)
        self.device_container.bind(minimum_height=self.device_container.setter('height'))
        scroll = ScrollView(size_hint_y=0.3)
        scroll.add_widget(self.device_container)
        self.add_widget(scroll)

        self.devices = {}
        self.pending_connections = {}
        self.br = None
        self.adapter = None
        self.cast_func = None
        self.bond_receiver = None
        if platform == 'android':
            Clock.schedule_once(self.deferred_init, 1)

    def _update_text_size(self, instance, size):
        instance.text_size = (size[0], None)

    def _on_msg_touch(self, instance, touch):
        if not instance.collide_point(*touch.pos):
            return False
        if touch.is_double_tap or (touch.time_end - touch.time_start > 0.5):
            if instance.text:
                Clipboard.copy(instance.text)
            return True
        return False

    def show_message(self, msg, color=(0,1,0,1)):
        @mainthread
        def _log():
            if self.msg_text.text:
                self.msg_text.text += '\n' + msg
            else:
                self.msg_text.text = msg
            self.msg_text.foreground_color = color
            self.msg_text.scroll_y = 0
        _log()

    def deferred_init(self, dt):
        try:
            from jnius import autoclass, cast
            from android.permissions import request_permissions, Permission
            from android.broadcast import BroadcastReceiver
            self.cast_func = cast
            Intent = autoclass('android.content.Intent')
            BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
            BluetoothDevice = autoclass('android.bluetooth.BluetoothDevice')
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            request_permissions([
                Permission.BLUETOOTH_SCAN,
                Permission.BLUETOOTH_CONNECT,
                Permission.ACCESS_FINE_LOCATION
            ])
            self.adapter = BluetoothAdapter.getDefaultAdapter()
            if self.adapter is None:
                self.show_message('[ERROR] No Bluetooth adapter', (1,0,0,1))
                return
            if not self.adapter.isEnabled():
                self.show_message('[INFO] Requesting BT enable...', (1,1,0,1))
                intent = Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE)
                PythonActivity.mActivity.startActivityForResult(intent, 1)
            else:
                self.show_message('[INFO] Bluetooth ready', (0,1,0,1))
            self._register_bond_receiver()
        except Exception as e:
            self.show_message(f'[ERROR] Init: {e}', (1,0,0,1))

    def _register_bond_receiver(self):
        try:
            from android.broadcast import BroadcastReceiver
            self.bond_receiver = BroadcastReceiver(
                self.on_bond_state_changed,
                actions=['android.bluetooth.device.action.BOND_STATE_CHANGED']
            )
            self.bond_receiver.start()
        except Exception as e:
            self.show_message(f'[ERROR] Register bond receiver: {e}', (1,0,0,1))

    def on_bond_state_changed(self, context, intent):
        try:
            if intent.getAction() != 'android.bluetooth.device.action.BOND_STATE_CHANGED':
                return
            device = intent.getParcelableExtra('android.bluetooth.device.extra.DEVICE')
            if not device:
                return
            dev = self.cast_func('android.bluetooth.BluetoothDevice', device)
            addr = dev.getAddress()
            bond_state = intent.getIntExtra('android.bluetooth.device.extra.BOND_STATE', -1)
            prev_state = intent.getIntExtra('android.bluetooth.device.extra.PREVIOUS_BOND_STATE', -1)
            self.show_message(f'[BOND] {dev.getName()} [{addr}] {prev_state} -> {bond_state}', (1,1,0,1))
            if bond_state == 12:
                if addr in self.pending_connections:
                    self.show_message(f'[BOND] Pairing completed for {dev.getName()}, connecting...', (0,1,0,1))
                    dev_to_connect = self.pending_connections.pop(addr)
                    Clock.schedule_once(lambda dt, d=dev_to_connect: self._do_connect(d), 0.5)
            elif bond_state == 10:
                if addr in self.pending_connections:
                    self.show_message(f'[BOND] Pairing failed for {dev.getName()}', (1,0,0,1))
                    self.pending_connections.pop(addr, None)
        except Exception as e:
            self.show_message(f'[ERROR] Bond callback: {e}', (1,0,0,1))

    def start_scan(self, instance):
        try:
            if not self.adapter:
                self.show_message('[ERROR] Adapter not ready', (1,0,0,1))
                return
            if not self.adapter.isEnabled():
                self.show_message('[ERROR] BT disabled', (1,0,0,1))
                return
            self.device_container.clear_widgets()
            self.devices.clear()
            from android.broadcast import BroadcastReceiver
            self.br = BroadcastReceiver(
                self.on_broadcast,
                actions=['android.bluetooth.device.action.FOUND']
            )
            self.br.start()
            self.adapter.startDiscovery()
            self.scan_btn.text = 'SCANNING...'
            self.scan_btn.disabled = True
            self.show_message('[INFO] Scanning...', (1,1,0,1))
            Clock.schedule_once(self.stop_scan, 12)
        except Exception as e:
            self.show_message(f'[ERROR] Scan start: {e}', (1,0,0,1))

    def stop_scan(self, dt):
        try:
            if self.adapter and self.adapter.isDiscovering():
                self.adapter.cancelDiscovery()
            if self.br:
                self.br.stop()
                self.br = None
            self.show_message('[INFO] Scan stopped', (1,1,0,1))
        except Exception as e:
            self.show_message(f'[ERROR] Stop scan: {e}', (1,0,0,1))
        finally:
            self.scan_btn.text = 'START SCAN'
            self.scan_btn.disabled = False

    def on_broadcast(self, context, intent):
        try:
            if intent.getAction() == 'android.bluetooth.device.action.FOUND':
                raw = intent.getParcelableExtra('android.bluetooth.device.extra.DEVICE')
                if raw:
                    dev = self.cast_func('android.bluetooth.BluetoothDevice', raw)
                    self.add_device(dev)
        except Exception as e:
            self.show_message(f'[ERROR] Broadcast: {e}', (1,0,0,1))

    @mainthread
    def add_device(self, dev):
        try:
            addr = dev.getAddress()
            if addr in self.devices:
                return
            self.devices[addr] = dev
            name = dev.getName() or 'Unknown'
            item = DeviceItem(name, addr, self.on_device_click)
            self.device_container.add_widget(item)
            self.show_message(f'[DEVICE] {name} [{addr}]', (0,1,0,1))
        except Exception as e:
            self.show_message(f'[ERROR] Add device: {e}', (1,0,0,1))

    def on_device_click(self, mac_addr):
        dev = self.devices.get(mac_addr)
        if dev:
            self.connect_device(dev)
        else:
            self.show_message('[ERROR] Device not found', (1,0,0,1))

    def connect_device(self, dev):
        try:
            bond_state = dev.getBondState()
            self.show_message(f'[INFO] Device {dev.getName()} bond state: {bond_state}', (1,1,0,1))
            if bond_state == 12:
                self._do_connect(dev)
            elif bond_state == 11:
                self.show_message(f'[INFO] Pairing in progress, waiting...', (1,1,0,1))
                self.pending_connections[dev.getAddress()] = dev
            elif bond_state == 10:
                self.show_message(f'[PAIR] Pairing with {dev.getName()}...', (1,1,0,1))
                self.pending_connections[dev.getAddress()] = dev
                if self.adapter.isDiscovering():
                    self.adapter.cancelDiscovery()
                dev.createBond()
            else:
                self.show_message(f'[ERROR] Unknown bond state: {bond_state}', (1,0,0,1))
        except Exception as e:
            self.show_message(f'[ERROR] Connect error: {e}', (1,0,0,1))

    def _do_connect(self, dev):
        threading.Thread(target=self._rfcomm_connect, args=(dev,), daemon=True).start()

    def _rfcomm_connect(self, dev):
        name = dev.getName() or 'Unknown'
        addr = dev.getAddress()
        try:
            from jnius import autoclass
            UUID = autoclass('java.util.UUID')
            SPP_UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")

            # 先打印设备支持的 UUID
            try:
                uuids = dev.getUuids()
                if uuids:
                    uuid_list = [str(u) for u in uuids]
                    Clock.schedule_once(lambda dt: self.show_message(f'[UUID] {name}: {", ".join(uuid_list)}', (0,1,1,1)))
                else:
                    Clock.schedule_once(lambda dt: self.show_message(f'[UUID] {name}: None (may be BLE)', (1,1,0,1)))
            except:
                pass

            # 取消扫描
            if self.adapter.isDiscovering():
                self.adapter.cancelDiscovery()
            time.sleep(0.3)

            # 方法1: 安全 RFCOMM
            try:
                socket = dev.createRfcommSocketToServiceRecord(SPP_UUID)
                socket.connect()
                Clock.schedule_once(lambda dt: self.show_message(f'[SUCCESS] Connected (secure) to {name}', (0,1,0,1)))
                return
            except Exception as e:
                Clock.schedule_once(lambda dt: self.show_message(f'[DEBUG] Secure fail: {str(e)[:80]}', (1,1,0,1)))

            # 方法2: 不安全 RFCOMM
            try:
                socket = dev.createInsecureRfcommSocketToServiceRecord(SPP_UUID)
                socket.connect()
                Clock.schedule_once(lambda dt: self.show_message(f'[SUCCESS] Connected (insecure) to {name}', (0,1,0,1)))
                return
            except Exception as e:
                Clock.schedule_once(lambda dt: self.show_message(f'[DEBUG] Insecure fail: {str(e)[:80]}', (1,1,0,1)))

            # 方法3: 反射多通道 (1-5)
            for channel in range(1, 6):
                try:
                    method = dev.getClass().getMethod("createRfcommSocket", [autoclass('int')])
                    socket = method.invoke(dev, [channel])
                    socket.connect()
                    Clock.schedule_once(lambda dt, ch=channel: self.show_message(f'[SUCCESS] Connected (reflection ch{ch}) to {name}', (0,1,0,1)))
                    return
                except Exception as e:
                    Clock.schedule_once(lambda dt, ch=channel: self.show_message(f'[DEBUG] Channel {ch} fail: {str(e)[:50]}', (1,1,0,1)))
                    continue

            # 所有方法都失败
            raise Exception("All connection methods (secure, insecure, channels 1-5) failed")

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            traceback.print_exc()
            Clock.schedule_once(lambda dt: self.show_message(
                f'[FATAL] Connection Error:\n{error_type}: {error_msg}', (1,0,0,1)))

    def on_pause(self):
        if self.br:
            self.br.stop()
        if self.bond_receiver:
            self.bond_receiver.stop()
        return True

    def on_resume(self):
        if self.br:
            self.br.start()
        if self.bond_receiver:
            self.bond_receiver.start()
        return True

class MainApp(App):
    def build(self):
        return BluetoothScanner()

if __name__ == '__main__':
    MainApp().run()