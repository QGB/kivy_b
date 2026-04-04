import sys
if 'qgb.U' not in sys.modules:
    sys.path.append('C:/QGB/Anaconda3/Lib/site-packages/Pythonwin/')
from qgb import *
N.rpcServer(globals=globals(), locals=locals(), port=1144)  # 不要动

from kivy.config import Config
Config.set('kivy', 'default_font', ['C:/Windows/Fonts/msyh.ttc'] * 4)
Config.write()

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

class DynamicAppLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)
        
        # 动态按钮区域
        self.add_widget(Label(text='动态按钮区域（点击下方按钮添加）', size_hint_y=0.1))
        scroll_btns = ScrollView(size_hint_y=0.4)
        self.button_container = BoxLayout(orientation='vertical', size_hint_y=None)
        self.button_container.bind(minimum_height=self.button_container.setter('height'))
        scroll_btns.add_widget(self.button_container)
        self.add_widget(scroll_btns)
        
        add_btn = Button(text='添加一个新按钮', size_hint_y=0.1)
        add_btn.bind(on_press=self.add_dynamic_button)
        self.add_widget(add_btn)
        
        # 动态列表区域
        self.add_widget(Label(text='动态列表（支持添加/删除）', size_hint_y=0.1))
        
        # 输入行
        input_layout = BoxLayout(orientation='horizontal', size_hint_y=0.1)
        self.list_input = TextInput(text='新项目', multiline=False)
        add_list_btn = Button(text='添加到列表')
        add_list_btn.bind(on_press=self.add_list_item)
        input_layout.add_widget(self.list_input)
        input_layout.add_widget(add_list_btn)
        self.add_widget(input_layout)
        
        # 列表容器（ScrollView + BoxLayout）
        scroll_list = ScrollView(size_hint_y=0.4)
        self.list_container = BoxLayout(orientation='vertical', size_hint_y=None)
        self.list_container.bind(minimum_height=self.list_container.setter('height'))
        scroll_list.add_widget(self.list_container)
        self.add_widget(scroll_list)
        
        # 预先添加示例按钮和列表项
        for i in range(3):
            self.add_dynamic_button(None, text=f'示例按钮 {i+1}')
        for i in range(5):
            self.add_list_item_by_text(f'列表项目 {i+1}')
    
    def add_dynamic_button(self, instance, text=None):
        btn_text = text if text else f'按钮 {len(self.button_container.children) + 1}'
        new_btn = Button(text=btn_text, size_hint_y=None, height=50)
        new_btn.bind(on_press=lambda x: print(f'点击了：{btn_text}'))
        self.button_container.add_widget(new_btn)
    
    def add_list_item(self, instance):
        text = self.list_input.text.strip()
        if text:
            self.add_list_item_by_text(text)
            self.list_input.text = ''
    
    def add_list_item_by_text(self, text):
        # 创建一个列表项（水平布局）
        item = BoxLayout(orientation='horizontal', size_hint_y=None, height=50)
        label = Label(text=text, size_hint_x=0.8)
        del_btn = Button(text='删除', size_hint_x=0.2)
        item.add_widget(label)
        item.add_widget(del_btn)
        self.list_container.add_widget(item)
        # 绑定删除事件
        del_btn.bind(on_press=lambda x: self.remove_list_item(item))
        # 动态调整容器高度（因为 size_hint_y=None 需要手动计算）
        self.list_container.height += 50
    
    def remove_list_item(self, item):
        if item.parent == self.list_container:
            self.list_container.remove_widget(item)
            self.list_container.height -= 50

class DynamicApp(App):
    def build(self):
        return DynamicAppLayout()

if __name__ == '__main__':
    DynamicApp().run()