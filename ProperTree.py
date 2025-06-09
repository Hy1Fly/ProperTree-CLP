#!/usr/bin/env python
import sys, os, binascii, base64, json, re, subprocess, webbrowser, multiprocessing, signal, ctypes
from collections import OrderedDict
try:
    import Tkinter as tk
    import ttk
    import tkFileDialog as fd
    import tkMessageBox as mb
    from tkFont import Font, families
    from tkColorChooser import askcolor as ac
except:
    import tkinter as tk
    import tkinter.ttk as ttk
    from tkinter import filedialog as fd
    from tkinter import messagebox as mb
    from tkinter.font import Font, families
    from tkinter.colorchooser import askcolor as ac
try:
    unicode
except NameError:  # Python 3
    unicode = str
# 将此脚本的目录添加到本地PATH变量 - 可提高导入一致性
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from Scripts import plist, plistwindow, downloader

def _check_for_update(queue, version_url = None, user_initiated = False):
    args = [sys.executable]
    file_path = os.path.join(os.path.abspath(os.path.dirname(__file__)),"Scripts","update_check.py")
    if os.path.exists(file_path):
        args.append(file_path)
    else:
        return queue.put({
            "exception":"找不到 update_check.py。",
            "error":"缺少必需文件",
            "user_initiated":user_initiated
        })
    if version_url: args.extend(["-u",version_url])
    proc = subprocess.Popen(args,stdout=subprocess.PIPE)
    o,e = proc.communicate()
    if sys.version_info >= (3,0): o = o.decode("utf-8")
    try:
        json_data = json.loads(o)
        # 追加/更新user_initiated值
        json_data["user_initiated"] = user_initiated
    except:
        return queue.put({
            "exception":"无法序列化返回的JSON数据。",
            "error":"检查更新时发生错误",
            "user_initiated":user_initiated
        })
    queue.put(json_data)

def _update_tex(queue, tex_url = None, tex_path = None):
    args = [sys.executable]
    file_path = os.path.join(os.path.abspath(os.path.dirname(__file__)),"Scripts","update_check.py")
    if os.path.exists(file_path):
        args.extend([file_path,"-m","tex","-t",tex_path])
    else:
        return queue.put({
            "exception":"找不到 update_check.py。",
            "error":"缺少必需文件"
        })
    if tex_url: args.extend(["-u",tex_url])
    proc = subprocess.Popen(args,stdout=subprocess.PIPE)
    o,e = proc.communicate()
    if sys.version_info >= (3,0): o = o.decode("utf-8")
    try:
        json_data = json.loads(o)
    except:
        return queue.put({
            "exception":"无法序列化返回的JSON数据。",
            "error":"下载Configuration.tex时发生错误"
        })
    queue.put(json_data)

class ProperTree:
    def __init__(self, plists = []):
        # 为多进程创建新队列
        self.queue = multiprocessing.Queue()
        self.tex_queue = multiprocessing.Queue()
        self.creating_window = False
        # 创建新的tk对象
        self.tk = tk.Tk()
        self.tk.withdraw() # 尝试在绘制前移除
        self.tk.title("值转换")
        self.tk.minsize(width=640,height=130)
        self.tk.resizable(True, False)
        self.tk.columnconfigure(2,weight=1)
        self.tk.columnconfigure(3,weight=1)
        # 构建十六进制 <--> Base64转换器
        f_label = tk.Label(self.tk, text="从:")
        f_label.grid(row=0,column=0,sticky="e",padx=10,pady=10)
        t_label = tk.Label(self.tk, text="到:")
        t_label.grid(row=1,column=0,sticky="e",padx=10,pady=10)

        # 创建设置窗口
        self.settings_window = tk.Toplevel(self.tk)
        self.settings_window.withdraw() # 尝试在绘制前移除
        self.settings_window.title("ProperTree 设置")
        self.settings_window.resizable(False, False)
        self.settings_window.columnconfigure(0,weight=1)
        self.settings_window.columnconfigure(2,weight=1)
        self.settings_window.columnconfigure(4,weight=1)
        self.settings_window.columnconfigure(6,weight=1)

        # 设置默认保留的最大撤销/重做步骤
        self.max_undo = 200
        
        # 设置选项列表的默认值
        self.allowed_types = ("XML","Binary")
        self.allowed_data  = ("Hex","Base64")
        self.allowed_int   = ("Decimal","Hex")
        self.allowed_bool  = ("True/False","YES/NO","On/Off","1/0",u"\u2714/\u274c")
        self.allowed_conv  = ("Ascii","Base64","Decimal","Hex","Binary")

        # 如果should_set_header_text()返回None，表示我们在macOS上运行
        # 窗口不支持原生深色模式，导致某些ttk小部件背景与窗口背景不匹配
        # 我们将尝试在这些情况下使用tk解决
        tk_or_ttk = tk if self.should_set_header_text() is None else ttk

        # 左侧 - 功能元素:
        
        # 添加复选框等
        sep_func = ttk.Separator(self.settings_window,orient="horizontal")
        sep_func.grid(row=0,column=1,columnspan=2,sticky="we",padx=10,pady=10)
        func_label = tk.Label(self.settings_window,text="功能选项:")
        func_label.grid(row=0,column=0,sticky="w",padx=10,pady=10)

        self.expand_on_open = tk.IntVar()
        self.use_xcode_data = tk.IntVar()
        self.sort_dict_keys = tk.IntVar()
        self.comment_ignore_case = tk.IntVar()
        self.comment_check_string = tk.IntVar()
        self.force_schema = tk.IntVar()
        self.expand_check = tk_or_ttk.Checkbutton(self.settings_window,text="打开Plist时展开子项",variable=self.expand_on_open,command=self.expand_command)
        self.xcode_check = tk_or_ttk.Checkbutton(self.settings_window,text="在XML Plist中使用Xcode样式<data>标签(内联)",variable=self.use_xcode_data,command=self.xcode_command)
        self.sort_check = tk_or_ttk.Checkbutton(self.settings_window,text="忽略字典键顺序",variable=self.sort_dict_keys,command=self.sort_command)
        self.ignore_case_check = tk_or_ttk.Checkbutton(self.settings_window,text="去除注释时忽略大小写",variable=self.comment_ignore_case,command=self.ignore_case_command)
        self.check_string_check = tk_or_ttk.Checkbutton(self.settings_window,text="去除注释时检查字符串值",variable=self.comment_check_string,command=self.check_string_command)
        self.expand_check.grid(row=1,column=0,columnspan=3,sticky="w",padx=10)
        self.xcode_check.grid(row=2,column=0,columnspan=3,sticky="w",padx=10)
        self.sort_check.grid(row=3,column=0,columnspan=3,sticky="w",padx=10)
        self.ignore_case_check.grid(row=4,column=0,columnspan=3,sticky="w",padx=10)
        self.check_string_check.grid(row=5,column=0,columnspan=3,sticky="w",padx=10)
        comment_prefix_label = tk.Label(self.settings_window,text="注释前缀(默认为#):")
        comment_prefix_label.grid(row=6,column=0,sticky="w",padx=10)
        self.comment_prefix_text = plistwindow.EntryPlus(self.settings_window,self.tk,self)
        self.comment_prefix_text.grid(row=6,column=1,columnspan=2,sticky="we",padx=10)
        self.plist_type_string = tk.StringVar(self.settings_window)
        self.plist_type_menu = tk_or_ttk.OptionMenu(self.settings_window, self.plist_type_string, *self.get_option_menu_list(self.allowed_types), command=self.change_plist_type)
        plist_label = tk.Label(self.settings_window,text="默认新建Plist类型:")
        plist_label.grid(row=7,column=0,sticky="w",padx=10)
        self.plist_type_menu.grid(row=7,column=1,columnspan=2,sticky="we",padx=10)
        self.data_type_string = tk.StringVar(self.settings_window)
        self.data_type_menu = tk_or_ttk.OptionMenu(self.settings_window, self.data_type_string, *self.get_option_menu_list(self.allowed_data), command=self.change_data_type)
        data_label = tk.Label(self.settings_window,text="数据显示默认:")
        data_label.grid(row=8,column=0,sticky="w",padx=10)
        self.data_type_menu.grid(row=8,column=1,columnspan=2,sticky="we",padx=10)
        self.int_type_string = tk.StringVar(self.settings_window)
        self.int_type_menu = tk_or_ttk.OptionMenu(self.settings_window, self.int_type_string, *self.get_option_menu_list(self.allowed_int), command=self.change_int_type)
        int_label = tk.Label(self.settings_window,text="整数显示默认:")
        int_label.grid(row=9,column=0,sticky="w",padx=10)
        self.int_type_menu.grid(row=9,column=1,columnspan=2,sticky="we",padx=10)
        self.bool_type_string = tk.StringVar(self.settings_window)
        self.bool_type_menu = tk_or_ttk.OptionMenu(self.settings_window, self.bool_type_string, *self.get_option_menu_list(self.allowed_bool), command=self.change_bool_type)
        bool_label = tk.Label(self.settings_window,text="布尔值显示默认:")
        bool_label.grid(row=10,column=0,sticky="w",padx=10)
        self.bool_type_menu.grid(row=10,column=1,columnspan=2,sticky="we",padx=10)
        self.snapshot_string = tk.StringVar(self.settings_window)
        self.snapshot_menu = tk_or_ttk.OptionMenu(self.settings_window, self.snapshot_string, "自动检测", command=self.change_snapshot_version)
        snapshot_label = tk.Label(self.settings_window,text="OC快照目标版本:")
        snapshot_label.grid(row=11,column=0,sticky="w",padx=10)
        self.snapshot_menu.grid(row=11,column=1,columnspan=2,sticky="we",padx=10)
        self.schema_check = tk_or_ttk.Checkbutton(self.settings_window,text="强制更新快照架构",variable=self.force_schema,command=self.schema_command)
        self.schema_check.grid(row=12,column=0,columnspan=3,sticky="w",padx=10)
        self.mod_check = tk.IntVar()
        self.enable_mod_check = tk_or_ttk.Checkbutton(self.settings_window,text="文件被外部修改时警告",variable=self.mod_check,command=self.mod_check_command)
        self.enable_mod_check.grid(row=13,column=0,columnspan=3,stick="w",padx=10)
        self.first_check = tk.IntVar()
        self.enable_first_check = tk_or_ttk.Checkbutton(self.settings_window,text="可能时在键之前编辑值",variable=self.first_check,command=self.first_check_command)
        self.enable_first_check.grid(row=14,column=0,columnspan=3,stick="w",padx=10)
        self.enable_drag_and_drop = tk.BooleanVar()
        self.toggle_drag_drop = tk_or_ttk.Checkbutton(self.settings_window,text="启用行拖放", variable=self.enable_drag_and_drop,command=self.drag_drop_command)
        self.toggle_drag_drop.grid(row=15,column=0,columnspan=3,sticky="w",padx=10)
        self.drag_label = tk.Label(self.settings_window,text="拖放死区(1-100像素):")
        self.drag_label.grid(row=16,column=0,sticky="w",padx=10)
        self.drag_pixels = tk.Label(self.settings_window,text="20")
        self.drag_pixels.grid(row=16,column=1,sticky="w",padx=(10,0))
        self.drag_scale = tk_or_ttk.Scale(self.settings_window,from_=1,to=100,orient=tk.HORIZONTAL,command=self.scale_command)
        # 尝试在使用tk时隐藏值 - 在ttk中会抛出异常
        try: self.drag_scale.configure(showvalue=False)
        except tk.TclError: pass
        self.drag_scale.grid(row=16,column=2,sticky="we",padx=(0,10))
        self.drag_disabled = tk.Label(self.settings_window,text="[拖放已禁用]")
        self.drag_disabled.configure(state="disabled")
        self.drag_disabled.grid(row=16,column=1,columnspan=2,sticky="we",padx=10)
        undo_max_label = tk.Label(self.settings_window,text="最大撤销(0=无限制, {}=默认):".format(self.max_undo))
        undo_max_label.grid(row=17,column=0,sticky="w",padx=10)
        self.undo_max_text = plistwindow.EntryPlus(self.settings_window,self.tk,self)
        self.undo_max_text.grid(row=17,column=1,columnspan=2,sticky="we",padx=10)
        
        # 左/右分隔符:
        sep = ttk.Separator(self.settings_window,orient="vertical")
        sep.grid(row=1,column=3,rowspan=17,sticky="ns",padx=10)

        # 右侧 - 主题元素:
        t_func = ttk.Separator(self.settings_window,orient="horizontal")
        t_func.grid(row=0,column=5,columnspan=2,sticky="we",padx=10,pady=10)
        tfunc_label = tk.Label(self.settings_window,text="外观选项:")
        tfunc_label.grid(row=0,column=4,sticky="w",padx=10,pady=10)

        self.op_label = tk.Label(self.settings_window,text="窗口不透明度(25-100%):")
        self.op_label.grid(row=1,column=4,sticky="w",padx=10)
        self.op_perc = tk.Label(self.settings_window,text="100")
        self.op_perc.grid(row=1,column=5,sticky="w",padx=(10,0))
        self.op_scale = tk_or_ttk.Scale(self.settings_window,from_=25,to=100,orient=tk.HORIZONTAL,command=self.update_opacity)
        # 尝试在使用tk时隐藏值 - 在ttk中会抛出异常
        try: self.op_scale.configure(showvalue=False)
        except tk.TclError: pass
        self.op_scale.grid(row=1,column=6,sticky="we",padx=10)
        r4_label = tk.Label(self.settings_window,text="高亮颜色:")
        r4_label.grid(row=2,column=4,sticky="w",padx=10)
        self.hl_canvas = tk.Canvas(self.settings_window, height=20, width=30, background="black", relief="groove", bd=2)
        self.hl_canvas.grid(row=2,column=5,columnspan=2,sticky="we",padx=10)
        r1_label = tk.Label(self.settings_window,text="交替行颜色 #1:")
        r1_label.grid(row=3,column=4,sticky="w",padx=10)
        self.r1_canvas = tk.Canvas(self.settings_window, height=20, width=30, background="black", relief="groove", bd=2)
        self.r1_canvas.grid(row=3,column=5,columnspan=2,sticky="we",padx=10)
        r2_label = tk.Label(self.settings_window,text="交替行颜色 #2:")
        r2_label.grid(row=4,column=4,sticky="w",padx=10)
        self.r2_canvas = tk.Canvas(self.settings_window, height=20, width=30, background="black", relief="groove", bd=2)
        self.r2_canvas.grid(row=4,column=5,columnspan=2,sticky="we",padx=10)
        r3_label = tk.Label(self.settings_window,text="列标题/背景颜色:")
        r3_label.grid(row=5,column=4,sticky="w",padx=10)
        self.bg_canvas = tk.Canvas(self.settings_window, height=20, width=30, background="black", relief="groove", bd=2)
        self.bg_canvas.grid(row=5,column=5,columnspan=2,sticky="we",padx=10)
        self.ig_bg_check = tk.IntVar()
        self.ig_bg = tk_or_ttk.Checkbutton(self.settings_window,text="标题文本忽略背景颜色",variable=self.ig_bg_check,command=self.check_ig_bg_command)
        self.ig_bg.grid(row=6,column=4,sticky="w",padx=10)
        self.bg_inv_check = tk.IntVar()
        self.bg_inv = tk_or_ttk.Checkbutton(self.settings_window,text="反转标题文本颜色",variable=self.bg_inv_check,command=self.check_bg_invert_command)
        self.bg_inv.grid(row=6,column=5,columnspan=2,sticky="w",padx=10)
        self.r1_inv_check = tk.IntVar()
        self.r1_inv = tk_or_ttk.Checkbutton(self.settings_window,text="反转行#1文本颜色",variable=self.r1_inv_check,command=self.check_r1_invert_command)
        self.r1_inv.grid(row=7,column=5,columnspan=2,sticky="w",padx=10)
        self.r2_inv_check = tk.IntVar()
        self.r2_inv = tk_or_ttk.Checkbutton(self.settings_window,text="反转行#2文本颜色",variable=self.r2_inv_check,command=self.check_r2_invert_command)
        self.r2_inv.grid(row=8,column=5,columnspan=2,sticky="w",padx=10)
        self.hl_inv_check = tk.IntVar()
        self.hl_inv = tk_or_ttk.Checkbutton(self.settings_window,text="反转高亮文本颜色",variable=self.hl_inv_check,command=self.check_hl_invert_command)
        self.hl_inv.grid(row=9,column=5,columnspan=2,sticky="w",padx=10)

        self.default_font = Font(font='TkTextFont')
        self.custom_font = tk.IntVar()
        self.font_check = tk_or_ttk.Checkbutton(self.settings_window,text="使用自定义字体大小",variable=self.custom_font,command=self.font_command)
        self.font_string = tk.StringVar()
        self.font_spinbox = tk.Spinbox(self.settings_window,from_=1,to=128,textvariable=self.font_string)
        try:
            self.font_string.trace_add("write",self.update_font)
        except AttributeError:
            self.font_string.trace("w",self.update_font)
        self.font_check.grid(row=10,column=4,sticky="w",padx=10)
        self.font_spinbox.grid(row=10,column=5,columnspan=2,sticky="we",padx=10)

        # 自定义字体选择器 - 复杂实现
        self.font_var = tk.IntVar()
        self.font_family  = tk.StringVar()
        self.font_custom_check = tk_or_ttk.Checkbutton(self.settings_window,text="使用自定义字体",variable=self.font_var,command=self.font_select)
        self.font_custom = ttk.Combobox(self.settings_window,state="readonly",textvariable=self.font_family,values=sorted(families()))
        self.font_custom.bind('<<ComboboxSelected>>',self.font_pick)
        try:
            self.font_family.trace_add("write",self.update_font_family)
        except AttributeError:
            self.font_family.trace("w",self.update_font_family)
        self.font_custom_check.grid(row=11,column=4,stick="w",padx=10)
        self.font_custom.grid(row=11,column=5,columnspan=2,sticky="we",padx=10)

        r5_label = tk.Label(self.settings_window,text="恢复外观默认值:")
        r5_label.grid(row=12,column=4,sticky="w",padx=10)
        dt_func = ttk.Separator(self.settings_window,orient="horizontal")
        dt_func.grid(row=12,column=5,columnspan=2,sticky="we",padx=10)

        default_font = tk_or_ttk.Button(self.settings_window,text="字体默认值",command=self.font_defaults)
        default_font.grid(row=13,column=4,sticky="we",padx=10)
        default_high = tk_or_ttk.Button(self.settings_window,text="高亮颜色",command=lambda:self.swap_colors("highlight"))
        default_high.grid(row=14,column=4,sticky="we",padx=10)
        default_light = tk_or_ttk.Button(self.settings_window,text="浅色模式颜色",command=lambda:self.swap_colors("light"))
        default_light.grid(row=13,column=5,columnspan=2,sticky="we",padx=10)
        default_dark = tk_or_ttk.Button(self.settings_window,text="深色模式颜色",command=lambda:self.swap_colors("dark"))
        default_dark.grid(row=14,column=5,columnspan=2,sticky="we",padx=10)

        sep_theme = ttk.Separator(self.settings_window,orient="horizontal")
        sep_theme.grid(row=18,column=0,columnspan=7,sticky="we",padx=10,pady=(10,0))

        # 添加检查更新复选框和按钮
        self.update_int = tk.IntVar()
        self.update_check = tk_or_ttk.Checkbutton(self.settings_window,text="启动时检查更新",variable=self.update_int,command=self.update_command)
        self.update_check.grid(row=19,column=0,sticky="w",padx=10,pady=(5,0))
        self.notify_once_int = tk.IntVar()
        self.notify_once_check = tk_or_ttk.Checkbutton(self.settings_window,text="每个版本仅通知一次",variable=self.notify_once_int,command=self.notify_once)
        self.notify_once_check.grid(row=20,column=0,sticky="w",padx=10,pady=(0,10))
        self.update_button = tk_or_ttk.Button(self.settings_window,text="立即检查",command=lambda:self.check_for_updates(user_initiated=True))
        self.update_button.grid(row=20,column=1,columnspan=2,sticky="w",padx=10,pady=(0,10))
        self.tex_button = tk_or_ttk.Button(self.settings_window,text="获取Configuration.tex",command=self.get_latest_tex)
        self.tex_button.grid(row=20,column=4,sticky="we",padx=10,pady=(0,10))
        reset_settings = tk_or_ttk.Button(self.settings_window,text="恢复所有默认值",command=self.reset_settings)
        reset_settings.grid(row=20,column=5,columnspan=2,sticky="we",padx=10,pady=(0,10))

        # 设置颜色选择器点击方法
        self.r1_canvas.bind("<ButtonRelease-1>",lambda x:self.pick_color("alternating_color_1",self.r1_canvas))
        self.r2_canvas.bind("<ButtonRelease-1>",lambda x:self.pick_color("alternating_color_2",self.r2_canvas))
        self.hl_canvas.bind("<ButtonRelease-1>",lambda x:self.pick_color("highlight_color",self.hl_canvas))
        self.bg_canvas.bind("<ButtonRelease-1>",lambda x:self.pick_color("background_color",self.bg_canvas))

        # 设置一些画布连接
        self.canvas_connect = {
            self.bg_canvas: {"invert":self.bg_inv_check},
            self.r1_canvas: {"invert":self.r1_inv_check},
            self.r2_canvas: {"invert":self.r2_inv_check},
            self.hl_canvas: {"invert":self.hl_inv_check}
        }
        
        self.default_dark  = {
            "alternating_color_1":"#161616",
            "alternating_color_2":"#202020",
            "highlight_color":"#1E90FF",
            "background_color":"#161616",
            "invert_background_text_color":False,
            "invert_row1_text_color":False,
            "invert_row2_text_color":False
        }
        self.default_light = {
            "alternating_color_1":"#F0F1F1",
            "alternating_color_2":"#FEFEFE",
            "highlight_color":"#1E90FF",
            "background_color":"#FEFEFE",
            "invert_background_text_color":False,
            "invert_row1_text_color":False,
            "invert_row2_text_color":False
        }

        # 设置从/到选项菜单
        self.f_title = tk.StringVar(self.tk)
        self.t_title = tk.StringVar(self.tk)
        f_option = tk_or_ttk.OptionMenu(self.tk, self.f_title, *self.get_option_menu_list(self.allowed_conv), command=self.change_from_type)
        t_option = tk_or_ttk.OptionMenu(self.tk, self.t_title, *self.get_option_menu_list(self.allowed_conv), command=self.change_to_type)
        f_option.grid(row=0,column=1,sticky="we")
        t_option.grid(row=1,column=1,sticky="we")

        self.f_text = plistwindow.EntryPlus(self.tk,self.tk,self)
        self.f_text.delete(0,tk.END)
        self.f_text.insert(0,"")
        self.f_text.grid(row=0,column=2,columnspan=3,sticky="we",padx=10,pady=10)

        self.t_text = plistwindow.EntryPlus(self.tk,self.tk,self)
        self.t_text.configure(state='normal')
        self.t_text.delete(0,tk.END)
        self.t_text.insert(0,"")
        self.t_text.configure(state='readonly')
        self.t_text.grid(row=1,column=2,columnspan=3,sticky="we",padx=10,pady=10)

        self.c_button = tk_or_ttk.Button(self.tk, text="转换", command=self.convert_values)
        self.c_button.grid(row=2,column=4,sticky="e",padx=10,pady=10)
        self.s_button = tk_or_ttk.Button(self.tk, text="交换方向", command=self.swap_convert)
        self.s_button.grid(row=2,column=0,columnspan=2,sticky="w",padx=10,pady=10)

        self.f_text.bind("<Return>", self.convert_values)
        self.f_text.bind("<KP_Enter>", self.convert_values)

        self.start_window = None

        # 从Finder打开时查找处理器序列号的正则表达式
        self.regexp = re.compile(r"^-psn_[0-9]+_[0-9]+$")

        # 设置菜单相关的键盘绑定 - 如果需要更改应用名称
        key="Control"
        sign = "Ctrl+"
        self.use_dark = self.get_dark()
        if str(sys.platform) == "darwin":
            # 将退出函数重新映射到我们自己的函数
            self.tk.createcommand('::tk::mac::Quit', self.quit)
            self.tk.createcommand("::tk::mac::OpenDocument", self.open_plist_from_app)
            self.tk.createcommand("::tk::mac::ShowPreferences", lambda:self.show_window(self.settings_window))
            # 导入更改包名称和强制焦点所需的模块
            try:
                from Foundation import NSBundle
                from Cocoa import NSRunningApplication, NSApplicationActivateIgnoringOtherApps
                app = NSRunningApplication.runningApplicationWithProcessIdentifier_(os.getpid())
                app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
                bundle = NSBundle.mainBundle()
                if bundle:
                    info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
                    if info and info['CFBundleName'] == 'Python':
                        info['CFBundleName'] = "ProperTree"
            except:
                pass
            key="Command"
            sign=key+"+"

        self.tk.protocol("WM_DELETE_WINDOW", lambda x=self.tk: self.close_window(window=x))
        self.settings_window.protocol("WM_DELETE_WINDOW", lambda x=self.settings_window: self.close_window(window=x))

        self.default_windows = (self.tk,self.settings_window)

        self.recent_menu = None
        if str(sys.platform) == "darwin":
            # 设置顶层菜单
            file_menu = tk.Menu(self.tk)
            main_menu = tk.Menu(self.tk)
            self.recent_menu = tk.Menu(self.tk)
            main_menu.add_cascade(label="文件", menu=file_menu)
            file_menu.add_command(label="新建 (Cmd+N)", command=self.new_plist)
            file_menu.add_command(label="打开 (Cmd+O)", command=self.open_plist)
            file_menu.add_cascade(label="打开最近", menu=self.recent_menu, command=self.open_recent)
            file_menu.add_command(label="保存 (Cmd+S)", command=self.save_plist)
            file_menu.add_command(label="另存为... (Cmd+Shift+S)", command=self.save_plist_as)
            file_menu.add_command(label="复制 (Cmd+D)", command=self.duplicate_plist)
            file_menu.add_command(label="从磁盘重新加载 (Cmd+L)", command=self.reload_from_disk)
            file_menu.add_separator()
            file_menu.add_command(label="OC快照 (Cmd+R)", command=self.oc_snapshot)
            file_menu.add_command(label="OC清理快照 (Cmd+Shift+R)", command=self.oc_clean_snapshot)
            file_menu.add_separator()
            file_menu.add_command(label="转换窗口 (Cmd+T)", command=lambda:self.show_window(self.tk))
            file_menu.add_command(label="去除注释 (Cmd+M)", command=self.strip_comments)
            file_menu.add_command(label="去除禁用条目 (Cmd+E)", command=self.strip_disabled)
            file_menu.add_command(label="去除键和值周围的空白 (Cmd+K)", command=lambda:self.strip_whitespace(keys=True,values=True))
            file_menu.add_separator()
            file_menu.add_command(label="设置 (Cmd+,)",command=lambda:self.show_window(self.settings_window))
            file_menu.add_separator()
            file_menu.add_command(label="切换查找/替换面板 (Cmd+F)",command=self.hide_show_find)
            file_menu.add_command(label="切换Plist/数据/整数类型面板 (Cmd+P)",command=self.hide_show_type)
            file_menu.add_separator()
            file_menu.add_command(label="退出 (Cmd+Q)", command=self.quit)
            self.tk.config(menu=main_menu)

        # 设置绑定
        # 在macOS上，tk 8.5支持<Command-Z>，但8.6需要<Shift-Command-z>
        # 可以通过同时包含Shift和大写字母来绕过
        self.tk.bind("<{}-w>".format(key), self.close_window)
        self.settings_window.bind("<{}-w>".format(key), self.close_window)
        self.tk.bind_all("<{}-n>".format(key), self.new_plist)
        self.tk.bind_all("<{}-o>".format(key), self.open_plist)
        self.tk.bind_all("<{}-s>".format(key), self.save_plist)
        self.tk.bind_all("<{}-Shift-S>".format(key), self.save_plist_as)
        self.tk.bind_all("<{}-d>".format(key), self.duplicate_plist)
        self.tk.bind_all("<{}-t>".format(key), lambda event, x=self.tk: self.show_window(x))
        self.tk.bind_all("<{}-z>".format(key), self.undo)
        self.tk.bind_all("<{}-Shift-Z>".format(key), self.redo)
        self.tk.bind_all("<{}-m>".format(key), self.strip_comments)
        self.tk.bind_all("<{}-e>".format(key), self.strip_disabled)
        self.tk.bind_all("<{}-k>".format(key), lambda x:self.strip_whitespace(keys=True,values=True))
        self.tk.bind_all("<{}-r>".format(key), self.oc_snapshot)
        self.tk.bind_all("<{}-Shift-R>".format(key), self.oc_clean_snapshot)
        self.tk.bind_all("<{}-l>".format(key), self.reload_from_disk)
        if not str(sys.platform) == "darwin":
            # 重写默认的Command-Q命令
            self.tk.bind_all("<{}-q>".format(key), self.quit)
            self.tk.bind_all("<{}-comma>".format(key), lambda event, x=self.settings_window:self.show_window(x))

        self.tk.bind("<KeyPress>", self.handle_keypress)
        self.settings_window.bind("<KeyPress>", self.handle_keypress)
        
        cwd = os.getcwd()
        os.chdir(os.path.abspath(os.path.dirname(__file__)))
        #
        # 加载设置 - 当前可用设置:
        # 
        # last_window_width:            宽度值(默认为640)
        # last_window_height:           高度值(默认为480)
        # expand_all_items_on_open:     布尔值
        # sort_dict:                    布尔值, false = OrderedDict
        # xcode_data:                   布尔值, true = <data>XXXX</data>, false = 不同行
        # comment_strip_prefix:         字符串, 默认为#
        # comment_strip_ignore_case:    布尔值, true = 去除注释时忽略大小写
        # comment_strip_check_string:   布尔值, true = 同时考虑字符串值
        # new_plist_default_type:       字符串, XML/Binary
        # display_data_as:              字符串, Hex/Base64
        # display_int_as:               字符串, Decimal/Hex
        # snapshot_version:             字符串, X.X.X版本号, 或Latest
        # force_snapshot_schema:        布尔值
        # alternating_color_1:          字符串, 深色: #161616 - 浅色: #F0F1F1
        # alternating_color_2:          字符串, 深色: #202020 - 浅色: #FEFEFE
        # highlight_color:              字符串, 深色: #1E90FF - 浅色: #1E90FF
        # background_color:             字符串, 深色: #161616 - 浅色: #FEFEFE
        # header_text_ignore_bg_color:  布尔值
        # invert_background_text_color: 布尔值
        # invert_row1_text_color:       布尔值
        # invert_row2_text_color:       布尔值
        # invert_hl_text_color:         布尔值
        # warn_if_modified:             布尔值
        # edit_values_before_keys:      布尔值
        # enable_drag_and_drop:         布尔值
        # drag_dead_zone:               拖动开始前的像素距离(默认为20)
        # open_recent:                  列表, 最近打开的路径
        # recent_max:                   整数, 最近项目的最大数量
        # max_undo:                     整数, 最大撤销历史 - 0 = 无限
        # check_for_updates_at_startup: 布尔值
        # notify_once_per_version:      布尔值
        # last_version_checked:         字符串
        # opacity                       整数, 10-100(默认为100)
        #

        self.settings = {}
        if os.path.exists("Scripts/settings.json"):
            try:
                self.settings = json.load(open("Scripts/settings.json"))
            except:
                pass
        # 同时加载快照默认值
        self.snapshot_data = {}
        if os.path.exists("Scripts/snapshot.plist"):
            try:
                with open("Scripts/snapshot.plist","rb") as f:
                    self.snapshot_data = plist.load(f)
            except:
                pass
        # 最后，如果存在version.json则加载
        self.version = {}
        if os.path.exists("Scripts/version.json"):
            try: self.version = json.load(open("Scripts/version.json"))
            except: pass
        os.chdir(cwd)

        # 将版本应用于更新和tex按钮
        self.reset_update_button()
        self.reset_tex_button()

        # 设置设置页面以反映我们的settings.json文件
        self.update_settings()

        self.case_insensitive = self.get_case_insensitive()
        # 规范化"打开最近"的路径
        self.normpath_recents()
        if str(sys.platform) == "darwin": self.update_recents()
        self.check_dark_mode()

        self.version_url = "https://raw.githubusercontent.com/corpnewt/ProperTree/master/Scripts/version.json"
        self.tex_url = "https://raw.githubusercontent.com/acidanthera/OpenCorePkg/master/Docs/Configuration.tex"
        self.repo_url = "https://github.com/corpnewt/ProperTree"

        # 在Windows上运行Python 2时，如果主脚本名称的大小写不正确，多进程可能会有问题:
        # 例如 Downloader.py 与 downloader.py
        #
        # 为了解决这个问题，我们尽可能尝试搜索正确的大小写
        try:
            path = os.path.abspath(sys.modules["__main__"].__file__)
            if os.path.isfile(path):
                name = os.path.basename(path).lower()
                fldr = os.path.dirname(path)
                for f in os.listdir(fldr):
                    if f.lower() == name:
                        sys.modules["__main__"].__file__ = os.path.join(fldr,f)
                        break
        except AttributeError as e:
            # 这可能意味着我们是直接从解释器运行的
            pass

        # 实现简单的布尔锁，并在需要时检查更新
        self.is_checking_for_updates = False
        if self.settings.get("check_for_updates_at_startup",True):
            self.tk.after(0, lambda:self.check_for_updates(user_initiated=False))

        # 先前的实现尝试等待250ms以给open_plist_from_app()足够的时间解析双击的内容
        # 问题是check_open()和open_plist_from_app()会大致同时触发 - 导致一个打开空白文档，另一个打开双击的plist
        # 我们现在使用is_opening锁来确定一个函数是否当前正在工作 - 另一个将在锁解除前每5ms检查一次再处理
        # 这允许我们覆盖另一个打开的空白文档 - 希望修复在macOS中双击时生成多个文档的问题
        self.is_opening = False
        self.is_quitting = False
        self.check_open(plists)
        
        # 为SIGINT设置信号处理程序，连接到我们的quit()函数
        signal.signal(signal.SIGINT,self.quit)
        # 设置事件循环"poke"以保持事件循环处理
        self.tk.after(200,self.sigint_check)

        # 设置标题栏颜色
        for w in (self.tk, self.settings_window):
            self.set_win_titlebar(windows=w)

        # 启动运行循环
        tk.mainloop()

    def _clipboard_append(self, clipboard_string = None):
        # Tkinter在复制到系统剪贴板时有已知问题，如错误报告中所述:
        # https://bugs.python.org/issue40452
        #
        # 有一些解决方法需要编译新的tk二进制文件 - 但我们可以
        # 通过调用clip或pbcopy(取决于当前操作系统)确保更新系统剪贴板
        #
        # 首先清除tkinter剪贴板
        self.tk.clipboard_clear()
        # 如果有值才写入tkinter剪贴板
        if clipboard_string: self.tk.clipboard_append(clipboard_string)
        else: clipboard_string = "" # 确保至少有一个空字符串
        # 为潜在的剪贴板命令收集参数 Windows -> macOS -> Linux
        for args in (["clip"],) if os.name=="nt" else (["pbcopy"],) if sys.platform=="darwin" else (["xclip","-sel","c"],["xsel","-ib"],):
            # 尝试启动子进程以镜像tkinter剪贴板内容
            try:
                clipboard = subprocess.Popen(
                    args,
                    stdin=subprocess.PIPE,
                    stderr=getattr(subprocess,"DEVNULL",open(os.devnull,"w")),
                    stdout=getattr(subprocess,"DEVNULL",open(os.devnull,"w"))
                )
            except:
                continue
            # 检查是否需要编码数据的Py2
            clipboard.stdin.write(clipboard_string if 2/3==0 else clipboard_string.encode())
            clipboard.stdin.flush() # 刷新缓冲区
            clipboard.stdin.close() # 关闭管道
            break # 按需跳出循环

    def sigint_check(self):
        # 辅助函数保持事件循环运行，以确保我们可以捕获KeyboardInterrupt
        self.tk.after(200,self.sigint_check)

    def get_case_insensitive(self):
        # 辅助函数检查文件路径，更改大小写，并查看os.path.exists()是否仍然有效
        our_path = os.path.abspath(__file__)
        # 遍历字符，找到第一个字母字符
        # 然后反转其大小写 - 并查看路径是否仍然存在
        for i,x in enumerate(our_path):
            if x.isalpha():
                x = x.upper() if x.islower() else x.lower()
                return os.path.exists(our_path[:i]+x+our_path[i+1:])
        # 如果到这里 - 路径中没有字母字符 - 我们只是...返回False以确保安全
        return False

    def check_dark_mode(self):
        check_dark = self.get_dark()
        if check_dark != self.use_dark and any((x not in self.settings for x in ("alternating_color_1","alternating_color_2","background_color"))):
            # 模式已更改
            # 按需更新颜色
            color_check = [x for x in self.default_dark if not x in self.settings]
            if color_check: # 有内容需要动画
                color_list = []
                from_dict,to_dict = (self.default_dark,self.default_light) if self.use_dark \
                               else (self.default_light,self.default_dark)
                for name in color_check:
                    if name.startswith("invert_"):
                        continue # 跳过布尔检查
                    color_list.append((
                        name,
                        from_dict[name],
                        to_dict[name]
                    ))
                # 排队动画
                self.color_animate(color_list)
            self.use_dark = check_dark
            if os.name == "nt":
                # 迭代所有窗口
                self.set_win_titlebar()
        # 每3秒继续循环
        self.tk.after(1500, lambda:self.check_dark_mode())

    def set_win_titlebar(self, windows=None, mode=None):
        if not os.name == "nt":
            return # 仅在Windows上更改
        if windows is None:
            windows = self.stackorder(self.tk, include_defaults=True)
        elif not isinstance(windows,(list,tuple)):
            windows = [windows]
        try:
            # 设置值
            if mode is None:
                mode = int(self.use_dark)
            value = ctypes.c_int(mode) # 模式0为浅色，1为深色
            # 配置窗口属性
            DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            set_window_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
            get_parent = ctypes.windll.user32.GetParent
        except:
            # 出错了 - 退出
            return
        for window in windows:
            try:
                # 更新窗口
                window.update()
                hwnd_inst = get_parent(window.winfo_id())
                set_window_attribute(hwnd_inst, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value),
                                    ctypes.sizeof(value))
                set_window_attribute(hwnd_inst, DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1, ctypes.byref(value),
                                    ctypes.sizeof(value))
                # 更新窗口大小以确保更改生效
                for x in (1,-1):
                    window.geometry("{}x{}".format(
                        window.winfo_width()+x,
                        window.winfo_height()+x
                    ))
                    window.update()
            except:
                # 出错了 - 但这只是装饰性的，
                # 所以我们继续正常进行
                continue

    def color_animate(self, colors, step=1, steps=5, delay=35):
        for name,start,end in colors:
            # 获取开始和结束作为整数 #rrggbb
            start_r = int(start[1:3],16)
            start_g = int(start[3:5],16)
            start_b = int(start[5:7],16)
            end_r = int(end[1:3],16)
            end_g = int(end[3:5],16)
            end_b = int(end[5:7],16)
            # 获取并应用步骤
            r_now = int((((end_r-start_r)/steps)*step)+start_r)
            g_now = int((((end_g-start_g)/steps)*step)+start_g)
            b_now = int((((end_b-start_b)/steps)*step)+start_b)
            # 设置目标颜色
            result = "#{}{}{}".format(
                hex(r_now)[2:].upper(),
                hex(g_now)[2:].upper(),
                hex(b_now)[2:].upper()
            )
            self.settings[name] = result
        # 更新窗口
        if step < steps:
            self.update_canvases()
            self.tk.after(delay, lambda:self.color_animate(
                colors, step=step+1, steps=steps, delay=delay
            ))
        else:
            # 移除调整后的颜色
            for c in colors:
                self.settings.pop(c[0],None)
            self.update_settings()

    def get_option_menu_list(self, option_list):
        # 辅助函数返回OptionMenu列表，取决于我们是否使用tk或ttk
        # 后者需要默认元素列出 - 我们将只选择option_list中的第一个元素
        if self.should_set_header_text() is None:
            # 这只应在macOS上当窗口不支持原生深色模式时发生
            return option_list
        # 我们应该使用ttk，它需要在选项之前有默认元素
        return [option_list[0]]+list(option_list)

    def should_set_header_text(self):
        # 在macOS中，标题颜色仅在特定Python构建的深色模式下受背景影响
        # 我们将尝试在此处获取系统的实际深色模式
        if str(sys.platform) != "darwin": return True # 在Windows/Linux上不更改
        try:
            # 询问窗口是否处于深色模式 - 仅在受支持时有效
            return bool(self.tk.call("tk::unsupported::MacWindowStyle","isdark",self.tk))
        except Exception as e:
            return None # 如果失败，窗口不支持深色模式

    def get_dark(self):
        if os.name=="nt":
            # 从注册表获取以告知我们是否处于深色/浅色模式
            p = subprocess.Popen(["reg","query","HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize","/v","AppsUseLightTheme"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            c = p.communicate()
            return c[0].decode("utf-8", "ignore").strip().lower().split(" ")[-1] in ("","0x0")
        elif str(sys.platform) != "darwin":
            return True # 在Linux平台上默认为深色模式
        # 获取macOS版本 - 并查看深色模式是否存在
        p = subprocess.Popen(["sw_vers","-productVersion"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        c = p.communicate()
        p_vers = c[0].decode("utf-8", "ignore").strip().lower()
        if p_vers < "10.14.0": return True # 在10.14之前的任何版本默认为深色
        # 此时 - 我们有一个支持深色模式的OS，让我们检查值
        p = subprocess.Popen(["defaults","read","-g","AppleInterfaceStyle"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        c = p.communicate()
        return c[0].decode("utf-8", "ignore").strip().lower() == "dark"

    def compare_version(self, v1, v2):
        # 按点分割版本号并比较每个值
        # 允许0.0.10 > 0.0.9，而普通字符串比较会返回false
        # 同时从每个段中去除任何非数字值以避免冲突
        #
        # 如果v1 > v2返回True，v1 == v2返回None，v1 < v2返回False
        if not all((isinstance(x,str) for x in (v1,v2))):
            # 错误类型
            return False
        v1_seg = v1.split(".")
        v2_seg = v2.split(".")
        # 用0填充以确保公共长度
        v1_seg += ["0"]*(len(v2_seg)-len(v1_seg))
        v2_seg += ["0"]*(len(v1_seg)-len(v2_seg))
        # 比较每个段 - 按需去除非数字
        for i in range(len(v1_seg)):
            a,b = v1_seg[i],v2_seg[i]
            try: a = int("".join([x for x in a if x.isdigit()]))
            except: a = 0
            try: b = int("".join([x for x in b if x.isdigit()]))
            except: b = 0
            if a > b: return True
            if a < b: return False
        # 如果到这里，两个版本相同
        return None

    def check_for_updates(self, user_initiated = False):
        if self.is_checking_for_updates: # 已在检查
            if user_initiated:
                # 我们按了按钮 - 但另一个检查正在进行
                self.tk.bell()
                mb.showerror("已在检查更新","更新检查已在运行。如果您在手动检查更新时持续遇到此错误 - 可能表示网络问题。")
                self.lift_window()
            return
        self.is_checking_for_updates = True # 锁定其他更新检查
        self.update_button.configure(
            state="disabled",
            text="检查中... ({})".format(self.version.get("version","?.?.?"))
        )
        # 利用多进程避免更新检查耗时过长导致UI锁定
        p = multiprocessing.Process(target=_check_for_update,args=(self.queue,self.version_url,user_initiated))
        p.daemon = True
        p.start()
        self.check_update_process(p)

    def reset_update_button(self):
        self.update_button.configure(
            state="normal",
            text="立即检查 ({})".format(self.version.get("version","?.?.?"))
        )

    def check_update_process(self, p):
        # 辅助函数监视直到更新完成
        if p.is_alive():
            self.tk.after(100,self.check_update_process,p)
            return
        # 加入进程以确保资源返回
        p.join()
        # 已返回 - 重置布尔锁
        self.is_checking_for_updates = False
        # 检查是否从队列中获取了内容
        if self.queue.empty(): # 队列中无内容，退出
            return self.reset_update_button()
        # 检索任何返回值并解析
        output_dict = self.queue.get()
        user_initiated = output_dict.get("user_initiated",False)
        # 检查是否有错误或异常
        if "exception" in output_dict or "error" in output_dict:
            error = output_dict.get("error","检查更新时发生错误")
            excep = output_dict.get("exception","检查更新时出错。")
            if user_initiated:
                self.tk.bell()
                mb.showerror(error,excep)
                self.lift_window()
            return self.reset_update_button()
        # 解析返回的输出
        version_dict = output_dict.get("json",{})
        if not version_dict.get("version"):
            if user_initiated:
                self.tk.bell()
                mb.showerror("检查更新时发生错误","返回的数据格式错误或不存在。")
                self.lift_window()
            return self.reset_update_button()
        # 此时 - 我们应该有包含版本键/值的json数据
        check_version = str(version_dict["version"]).lower()
        our_version   = str(self.version.get("version","0.0.0")).lower()
        notify_once   = self.settings.get("notify_once_per_version",True)
        last_version  = str(self.settings.get("last_version_checked","0.0.0")).lower()
        if self.compare_version(check_version,our_version) is True:
            if notify_once and last_version == check_version and not user_initiated:
                # 已通知此版本 - 忽略
                return self.reset_update_button()
            # 保存最后检查的版本
            self.settings["last_version_checked"] = check_version
            # 我们有一个未忽略的更新 - 提示
            self.tk.bell()
            result = mb.askyesno(
                title="有新版本ProperTree可用",
                message="版本 {} 可用 (当前为 {})。\n\n{}中的新内容:\n{}\n\n现在访问ProperTree的github仓库?".format(
                    check_version,
                    our_version,
                    check_version,
                    version_dict.get("changes","未列出更改。")
                )
            )
            if result: # 在默认浏览器中打开URL
                webbrowser.open(self.repo_url)

        elif user_initiated:
            # 无新更新 - 但我们需要告知用户
            mb.showinfo(
                title="无可用更新",
                message="您当前运行的是最新版本的ProperTree ({}).".format(our_version)
            )
        
        else:
            # 无通知 - 且非用户发起
            return self.reset_update_button()
        
        # 通知后重置更新按钮
        self.reset_update_button()
        # 如果到这里 - 我们显示了某些消息，将窗口置顶
        self.lift_window()

    def get_best_tex_path(self):
        pt_path = os.path.abspath(os.path.dirname(__file__))
        # 添加脚本旁边的检查
        config_tex_paths = [os.path.join(pt_path,"Configuration.tex")]
        pt_path_parts = pt_path.split(os.sep)
        if len(pt_path_parts) >= 3 and pt_path_parts[-2:] == ["Contents","MacOS"] \
            and pt_path_parts[-3].lower().endswith(".app"):
            for x in range(3):
                # 移除最后3个路径组件，因为我们在.app包中
                pt_path = os.path.dirname(pt_path)
                # 添加.app包旁边的检查
                config_tex_paths.append(os.path.join(pt_path,"Configuration.tex"))
        # 迭代需要检查的路径并返回第一个匹配项
        for path in config_tex_paths:
            if os.path.isfile(path):
                return path
        # 如果未找到 - 返回第一个条目
        if config_tex_paths:
            return config_tex_paths[0]

    def get_tex_version(self, file_path = None):
        file_path = file_path or self.get_best_tex_path()
        if not file_path or not os.path.isfile(file_path):
            return None
        try:
            with open(file_path,"r") as f:
                t = f.read()
            for line in t.split("\n"):
                line = line.strip().lower()
                if line.startswith("reference manual (") and line.endswith(")"):
                    return line.split("(")[-1].split(")")[0]
        except: pass
        return None

    def reset_tex_button(self, version = None):
        tex_version = version or self.get_tex_version()
        self.tex_button.configure(
            state="normal",
            text="获取Configuration.tex{}".format(
                " ({})".format(tex_version) if tex_version else ""
            )
        )

    def get_latest_tex(self):
        tex_version = self.get_tex_version()
        self.tex_button.configure(
            state="disabled",
            text="下载中...{}".format(
                " ({})".format(tex_version) if tex_version else ""
            )
        )
        # 利用多进程避免更新检查耗时过长导致UI锁定
        p = multiprocessing.Process(target=_update_tex,args=(self.tex_queue,self.tex_url,self.get_best_tex_path()))
        p.daemon = True
        p.start()
        self.check_tex_process(p)

    def check_tex_process(self, p):
        # 辅助函数监视直到更新完成
        if p.is_alive():
            self.tk.after(100,self.check_tex_process,p)
            return
        # 加入进程以确保资源返回
        p.join()
        # 检查是否从队列中获取了内容
        if self.tex_queue.empty(): # 队列中无内容，退出
            return self.reset_tex_button()
        output_dict = self.tex_queue.get()
        # 检查是否有错误或异常
        if "exception" in output_dict or "error" in output_dict:
            error = output_dict.get("error","下载Configuration.tex时发生错误")
            excep = output_dict.get("exception","获取最新Configuration.tex时出错。")
            self.tk.bell()
            mb.showerror(error,excep)
        else:
            tex_path = self.get_best_tex_path()
            if os.path.isfile(tex_path):
                version = self.get_tex_version(file_path=tex_path)
                if not version:
                    self.tk.bell()
                    mb.showerror(
                        title="下载Configuration.tex时发生错误",
                        message="获取最新Configuration.tex时出错。"
                    )
                else:
                    mb.showinfo(
                        title="已更新Configuration.tex",
                        message="Configuration.tex ({}) 已保存到:\n\n{}".format(version,tex_path)
                    )
        self.reset_tex_button()
        # 如果到这里 - 我们显示了某些消息，将窗口置顶
        self.lift_window()

    def handle_keypress(self, event, generate=True):
        if event.state & 0x2 and event.keysym != "Caps_Lock":
            # 检查我们所在的OS并去除不关心的修饰键
            state_bitmask = 0xFFFFFFFF
            if os.name == "nt":
                state_bitmask -= 0x8  # Num Lock
                state_bitmask -= 0x20 # Scroll Lock
            elif sys.platform == "darwin":
                state_bitmask -= 0x20 # Num Lock
            else: # 假定Linux
                state_bitmask -= 0x10 # Num Lock
            state_bitmask -= 0x2 # 在所有平台上去除Caps Lock
            event.state &= state_bitmask
            # 构建序列 - 修改自:
            #  - https://github.com/python/cpython/blob/3.13/Lib/tkinter/__init__.py
            mods = ('Shift', 'Lock', 'Control',
                    'Mod1', 'Mod2', 'Mod3', 'Mod4', 'Mod5',
                    'Button1', 'Button2', 'Button3', 'Button4', 'Button5')
            s = []
            for i, n in enumerate(mods):
                if event.state & (1 << i):
                    s.append(n)
            # 如果只有一个字符，则获取小写keysym
            keysym = event.keysym.lower() if len(event.keysym)==1 else event.keysym
            sequence = "<{}{}Key-{}>".format(
                "-".join(s),
                "-" if s else "",
                keysym
            )
            # 首先检查我们构建的序列的bind_all
            if sequence in event.widget.bind_all():
                # 仅传播事件
                event.widget.event_generate(sequence)
                return "break"
            # 遍历每个小部件及其父项，查找刚构建的绑定序列
            parent = event.widget
            while True:
                if sequence in parent.bind():
                    parent.event_generate(sequence)
                    return "break"
                parent_name = parent.winfo_parent()
                if not parent_name:
                    return # 退出 - 小部件外
                parent = parent._nametowidget(parent_name)

    def text_color(self, hex_color, invert = False):
        hex_color = hex_color.lower()
        if hex_color.startswith("0x"): hex_color = hex_color[2:]
        if hex_color.startswith("#"): hex_color = hex_color[1:]
        # 检查无效十六进制，默认返回"black"
        if len(hex_color) != 6 or not all((x in "0123456789abcdef" for x in hex_color)):
            return "white" if invert else "black"
        # 获取r、g和b值并确定伪亮度
        r = float(int(hex_color[0:2],16))
        g = float(int(hex_color[2:4],16))
        b = float(int(hex_color[4:6],16))
        l = (r*0.299 + g*0.587 + b*0.114) > 186
        if l: return "white" if invert else "black"
        return "black" if invert else "white"

    def set_window_opacity(self, opacity=None, window=None):
        if opacity is None:
            try: opacity = min(100,max(int(self.settings.get("opacity",100)),25))
            except: opacity = 100 # 安全措施
        if window:
            # 仅使用传递的窗口
            if isinstance(window,(list,tuple)):
                windows = window
            else: # 包装成元组
                windows = (window,)
        else:
            # 确保设置默认窗口的不透明度，无论是否可见
            windows = self.stackorder(self.tk,include_defaults=False) + [self.tk, self.settings_window]
        for window in windows:
            window.attributes("-alpha",float(opacity)/float(100))

    def update_opacity(self, event = None):
        self.settings["opacity"] = self.op_scale.get()
        self.set_window_opacity(self.settings["opacity"])
        self.op_perc.configure(
            text="{}".format(str(int(self.op_scale.get())).rjust(3))
        )

    def expand_command(self, event = None):
        self.settings["expand_all_items_on_open"] = True if self.expand_on_open.get() else False

    def xcode_command(self, event = None):
        self.settings["xcode_data"] = True if self.use_xcode_data.get() else False

    def sort_command(self, event = None):
        self.settings["sort_dict"] = True if self.sort_dict_keys.get() else False

    def ignore_case_command(self, event = None):
        self.settings["comment_strip_ignore_case"] = True if self.comment_ignore_case.get() else False

    def check_string_command(self, event = None):
        self.settings["comment_strip_check_string"] = True if self.comment_check_string.get() else False

    def drag_drop_command(self, event = None):
        self.settings["enable_drag_and_drop"] = True if self.enable_drag_and_drop.get() else False
        self.scale_command() # 确保比例尺被反映
        if self.enable_drag_and_drop.get():
            self.drag_scale.grid()
            self.drag_disabled.grid_remove()
        else:
            self.drag_disabled.grid()
            self.drag_scale.grid_remove()

    def scale_command(self, event = None):
        self.settings["drag_dead_zone"] = self.drag_scale.get()
        self.drag_pixels.configure(
            text="{}".format(str(int(self.drag_scale.get())).rjust(3)) if self.enable_drag_and_drop.get() else ""
        )

    def check_ig_bg_command(self, event = None):
        self.settings["header_text_ignore_bg_color"] = True if self.ig_bg_check.get() else False
        self.update_colors()

    def check_bg_invert_command(self, event = None):
        self.settings["invert_background_text_color"] = True if self.bg_inv_check.get() else False
        self.update_colors()

    def check_r1_invert_command(self, event = None):
        self.settings["invert_row1_text_color"] = True if self.r1_inv_check.get() else False
        self.update_colors()

    def check_r2_invert_command(self, event = None):
        self.settings["invert_row2_text_color"] = True if self.r2_inv_check.get() else False
        self.update_colors()

    def check_hl_invert_command(self, event = None):
        self.settings["invert_hl_text_color"] = True if self.hl_inv_check.get() else False
        self.update_colors()

    def schema_command(self, event = None):
        self.settings["force_snapshot_schema"] = True if self.force_schema.get() else False

    def mod_check_command(self, event = None):
        self.settings["warn_if_modified"] = True if self.mod_check.get() else False

    def first_check_command(self, event = None):
        self.settings["edit_values_before_keys"] = True if self.first_check.get() else False

    def update_command(self, event = None):
        self.settings["check_for_updates_at_startup"] = True if self.update_int.get() else False
        self.update_notify()

    def notify_once(self, event = None):
        self.settings["notify_once_per_version"] = True if self.notify_once_int.get() else False

    def update_notify(self):
        self.notify_once_check.configure(state="normal" if self.update_int.get() else "disabled")

    def change_plist_type(self, event = None):
        self.settings["new_plist_default_type"] = self.plist_type_string.get()

    def change_data_type(self, event = None):
        self.settings["display_data_as"] = self.data_type_string.get()

    def change_int_type(self, event = None):
        self.settings["display_int_as"] = self.int_type_string.get()

    def change_bool_type(self, event = None):
        self.settings["display_bool_as"] = self.bool_type_string.get()

    def change_snapshot_version(self, event = None):
        self.settings["snapshot_version"] = self.snapshot_string.get().split(" ")[0]

    def font_command(self, event = None):
        if self.custom_font.get():
            self.settings["use_custom_font_size"] = True
            self.font_spinbox.configure(state="normal")
        else:
            self.settings["use_custom_font_size"] = False
            self.font_spinbox.configure(state="disabled")
            # self.font_string.set(self.default_font["size"])
            self.settings.pop("font_size",None)
        self.update_font()

    def font_select(self, event = None):
        if self.font_var.get():
            self.settings["use_custom_font"] = True
            self.settings["font_family"] = self.font_family.get()
            self.font_custom.configure(state='readonly')
        else:
            self.settings["use_custom_font"] = False
            self.font_custom.configure(state='disabled')
            self.settings.pop("font_family",None)
        self.update_font_family()

    def font_pick(self, event = None):
        font_family = self.font_family.get()
        if self.settings["font_family"] == font_family:
            return
        self.settings["font_family"] = font_family
        self.update_font_family()

    def update_font(self, var = None, blank = None, trace_mode = None):
        try:
            input_size = int(self.font_string.get())
            font_size = max(min(128,input_size),1)
            if font_size != input_size:
                self.font_string.set(str(font_size))
        except:
            return
        self.settings["font_size"] = font_size
        self.update_fonts()

    def update_font_family(self, event = None, blank = None, trace_mode = None):
        windows = self.stackorder(self.tk)
        if not len(windows): return
        for window in windows:
            if window in self.default_windows: continue
            window.set_font_family()

    def font_defaults(self, event = None):
        self.settings["use_custom_font"] = False
        self.settings.pop("font_family",None)
        self.settings["use_custom_font_size"] = False
        self.settings.pop("font_size",None)
        self.update_settings()

    def pick_color(self, color_name = None, canvas = None):
        if not color_name or not canvas: return # 什么?
        _,color = ac(color=canvas["background"])
        if not color: return # 用户取消
        self.settings[color_name] = color
        canvas.configure(background=color)
        self.update_colors()

    def swap_colors(self, color_type = None):
        if not isinstance(color_type,str): return
        color_type = color_type.lower()
        if color_type == "highlight":
            self.settings.pop("highlight_color",None)
            self.settings.pop("invert_hl_text_color",None)
            return self.update_settings()
        # 找出我们是否设置为浅色或深色模式 - 如果在macOS/Windows上使用系统当前设置，
        # 移除它们以使用默认值
        self.use_dark = self.get_dark()
        color_dict = self.default_light if color_type == "light" else self.default_dark
        to_remove = (self.use_dark and color_type == "dark") or (not self.use_dark and color_type != "dark")
        for x in color_dict:
            if color_type != "highlight" and x.lower() == "highlight_color": continue
            if to_remove: self.settings.pop(x,None)
            else: self.settings[x] = color_dict[x]
        self.update_settings()

    def update_canvases(self):
        default_color = self.default_dark if self.use_dark else self.default_light
        color_1 = "".join([x for x in self.settings.get("alternating_color_1",default_color["alternating_color_1"]) if x.lower() in "0123456789abcdef"])
        color_2 = "".join([x for x in self.settings.get("alternating_color_2",default_color["alternating_color_2"]) if x.lower() in "0123456789abcdef"])
        color_h = "".join([x for x in self.settings.get("highlight_color"    ,default_color["highlight_color"    ]) if x.lower() in "0123456789abcdef"])
        color_b = "".join([x for x in self.settings.get("background_color"   ,default_color["background_color"   ]) if x.lower() in "0123456789abcdef"])
        self.r1_canvas.configure(background="#"+color_1 if len(color_1) == 6 else default_color["alternating_color_1"])
        self.r2_canvas.configure(background="#"+color_2 if len(color_2) == 6 else default_color["alternating_color_2"])
        self.hl_canvas.configure(background="#"+color_h if len(color_h) == 6 else default_color["highlight_color"])
        self.bg_canvas.configure(background="#"+color_b if len(color_b) == 6 else default_color["background_color"])
        self.ig_bg_check.set(self.settings.get("header_text_ignore_bg_color",False))
        self.bg_inv_check.set(self.settings.get("invert_background_text_color",False))
        self.r1_inv_check.set(self.settings.get("invert_row1_text_color",False))
        self.r2_inv_check.set(self.settings.get("invert_row2_text_color",False))
        self.hl_inv_check.set(self.settings.get("invert_hl_text_color",False))
        self.update_colors()

    def reset_settings(self, event = None):
        self.settings = {}
        self.update_settings()

    def update_settings(self):
        self.expand_on_open.set(self.settings.get("expand_all_items_on_open",True))
        self.use_xcode_data.set(self.settings.get("xcode_data",True))
        self.sort_dict_keys.set(self.settings.get("sort_dict",False))
        def_type = self.settings.get("new_plist_default_type",self.allowed_types[0])
        self.plist_type_string.set(def_type if def_type in self.allowed_types else self.allowed_types[0])
        dat_type = self.settings.get("display_data_as",self.allowed_data[0])
        self.data_type_string.set(dat_type if dat_type in self.allowed_data else self.allowed_data[0])
        int_type = self.settings.get("display_int_as",self.allowed_int[0])
        self.int_type_string.set(int_type if int_type in self.allowed_int else self.allowed_int[0])
        bool_type = self.settings.get("display_bool_as",self.allowed_bool[0])
        self.bool_type_string.set(bool_type if bool_type in self.allowed_bool else self.allowed_bool[0])
        conv_f_type = self.settings.get("convert_from_type",self.allowed_conv[1])
        self.f_title.set(conv_f_type if conv_f_type in self.allowed_conv else self.allowed_conv[1])
        conv_t_type = self.settings.get("convert_to_type",self.allowed_conv[-1])
        self.t_title.set(conv_t_type if conv_t_type in self.allowed_conv else self.allowed_conv[-1])
        self.snapshot_menu["menu"].delete(0,"end")
        snapshot_versions = ["{} -> {}".format(x["min_version"],x.get("max_version","当前")) if x["min_version"]!=x.get("max_version","当前") else x["min_version"] for x in self.snapshot_data if "min_version" in x and len(x["min_version"])]
        snapshot_choices = ["自动检测","最新"] + sorted(snapshot_versions,reverse=True)
        for choice in snapshot_choices:
            self.snapshot_menu["menu"].add_command(label=choice,command=tk._setit(self.snapshot_string,choice,self.change_snapshot_version))
        snapshot_vers = self.settings.get("snapshot_version","自动检测")
        snapshot_name = next((x for x in snapshot_choices if x.split(" ")[0] == snapshot_vers),None)
        self.snapshot_string.set(snapshot_name if snapshot_name in snapshot_choices else "自动检测")
        self.force_schema.set(self.settings.get("force_snapshot_schema",False))
        self.mod_check.set(self.settings.get("warn_if_modified",True))
        self.first_check.set(self.settings.get("edit_values_before_keys",False))
        self.comment_ignore_case.set(self.settings.get("comment_strip_ignore_case",False))
        self.comment_check_string.set(self.settings.get("comment_strip_check_string",True))
        self.update_int.set(self.settings.get("check_for_updates_at_startup",True))
        self.notify_once_int.set(self.settings.get("notify_once_per_version",True))
        self.update_notify()
        self.comment_prefix_text.delete(0,tk.END)
        prefix = self.settings.get("comment_strip_prefix","#")
        prefix = "#" if not prefix else prefix
        self.comment_prefix_text.insert(0,prefix)
        self.undo_max_text.delete(0,tk.END)
        max_undo = self.settings.get("max_undo",self.max_undo)
        max_undo = self.max_undo if not isinstance(max_undo,int) or max_undo < 0 else max_undo
        self.undo_max_text.insert(0,str(max_undo))
        try: opacity = min(100,max(int(self.settings.get("opacity",100)),25))
        except: opacity = 100 # 安全措施
        self.op_scale.set(opacity)
        self.set_window_opacity(opacity)
        self.enable_drag_and_drop.set(self.settings.get("enable_drag_and_drop",True))
        self.drag_scale.set(self.settings.get("drag_dead_zone",20))
        self.drag_drop_command() # 确保drag_scale状态按需更新
        try:
            font_size = max(min(128,int(self.settings.get("font_size"))),1)
        except:
            font_size = self.default_font["size"]
        self.font_string.set(font_size)
        self.custom_font.set(self.settings.get("use_custom_font_size",False))
        self.font_family.set(self.settings.get("font_family",self.default_font.actual()["family"]))
        self.font_var.set(self.settings.get("use_custom_font",False))
        self.font_command()
        self.font_select()
        self.update_canvases()

    def update_canvas_text(self, canvas = None):
        if canvas is None: # 更新所有
            canvas = (self.bg_canvas,self.r1_canvas,self.r2_canvas,self.hl_canvas)
        if not isinstance(canvas, (tuple,list)): canvas = (canvas,)
        for c in canvas:
            if not c in self.canvas_connect: continue # 未识别的画布 - 跳过
            # 按需更新每个画布 - 但注意文本颜色
            color = self.text_color(c["background"],self.canvas_connect[c]["invert"].get())
            if self.canvas_connect[c].get("text_id",None) is None: # 尚未绘制 - 尝试
                # 获取大小
                w = self.settings_window.winfo_width()
                h = c.winfo_height()
                if w==1==h: # 请求宽度，因为尚未绘制
                    w = self.settings_window.winfo_reqwidth()
                    h = c.winfo_reqheight()
                    cw = c.winfo_reqwidth()
                    # 未绘制 - 估算位置并为macOS和Win/Linux填充最佳猜测
                    rw = int(w/2) if str(sys.platform)=="darwin" else int(w/2-cw/2)
                else:
                    # 已绘制，计算新方式 - 小部件宽度/2给出中点
                    cw = c.winfo_width()
                    rw = int(cw/2)
                self.canvas_connect[c]["text_id"] = c.create_text(rw,int(h/2),text="示例文本")
            # 设置颜色
            c.itemconfig(self.canvas_connect[c]["text_id"], fill=color)

    def update_fonts(self):
        windows = self.stackorder(self.tk,include_defaults=True)
        if not len(windows): return
        font = Font(family=self.font_family.get()) if self.font_var.get() else Font(font="TkTextFont")
        font["size"] = self.font_string.get() if self.custom_font.get() else self.default_font["size"]
        for window in windows:
            if window in self.default_windows: continue
            form_text = next((x for x in window.winfo_children() if str(x).endswith("!formattedtext")),None)
            if form_text: # 我们需要在此手动设置文本颜色
                form_text.update_font(font)
            else:
                window.set_font_size()

    def update_colors(self):
        self.update_canvas_text()
        # 更新所有窗口的颜色
        windows = self.stackorder(self.tk,include_defaults=True)
        if not len(windows):
            # 无事可做
            return
        # 按需为FormattedText小部件获取文本颜色
        r1  = self.r1_canvas["background"]
        r1t = self.text_color(r1,invert=self.r1_inv_check.get())
        for window in windows:
            if window in self.default_windows: continue
            form_text = next((x for x in window.winfo_children() if str(x).endswith("!formattedtext")),None)
            if form_text: # 我们需要在此手动设置文本颜色
                form_text.configure(bg=r1,fg=r1t)
            else: # 只有标准窗口 - 无格式文本更新
                window.set_colors()

    def compare_paths(self,check,path):
        if not isinstance(path,(str,unicode,list)): return False
        if self.case_insensitive:
            check = check.lower()
            path = path.lower() if isinstance(path,(str,unicode)) else [x.lower() for x in path]
        return check in path if isinstance(path,list) else check == path

    def normpath_recents(self):
        normalized = [os.path.normpath(x) for x in self.settings.get("open_recent",[])]
        new_paths = []
        for path in normalized:
            if self.compare_paths(path,new_paths): continue # 不添加重复项
            new_paths.append(path)
        self.settings["open_recent"] = new_paths

    def update_recents(self):
        # 辅助函数确定要更新的菜单，并实际更新
        targets = [self] if str(sys.platform) == "darwin" else [w for w in self.stackorder(self.tk) if not w in self.default_windows]
        for target in targets:
            self.update_recents_for_target(target)

    def update_recents_for_target(self,target):
        if not hasattr(target,"recent_menu"): return # 无效目标?
        # 辅助函数为目标菜单设置"打开最近"菜单
        recents = self.settings.get("open_recent",[])
        target.recent_menu.delete(0,tk.END)
        if not len(recents):
            target.recent_menu.add_command(label="无最近打开的文件", state=tk.DISABLED)
        else:
            for recent in recents:
                target.recent_menu.add_command(label=recent, command=lambda x=recent:self.open_recent(x))
        # 添加分隔符和清除选项
        target.recent_menu.add_separator()
        target.recent_menu.add_command(label="清除最近打开", command=self.clear_recents)

    def add_recent(self,recent):
        # 添加新项目到"打开最近"列表，确保列表不超过recent_max值
        recent = os.path.normpath(recent) # 规范化路径
        recents = [x for x in self.settings.get("open_recent",[]) if not self.compare_paths(recent,x)]
        recents.insert(0,recent)
        recent_max = self.settings.get("recent_max",10)
        recents = recents[:recent_max]
        self.settings["open_recent"] = recents
        self.update_recents()

    def rem_recent(self,recent):
        # 如果存在，则从"打开最近"列表中移除
        recent = os.path.normpath(recent) # 规范化路径
        recents = [x for x in self.settings.get("open_recent",[]) if not x == recent]
        self.settings["open_recent"] = recents
        self.update_recents()

    def clear_recents(self):
        self.settings.pop("open_recent",None)
        self.update_recents()

    def open_recent(self, path=None):
        # 首先检查文件是否存在 - 如果不存在，抛出错误，并从最近菜单中移除
        if path is None: # 尝试从设置中获取第一个项目
            paths = self.settings.get("open_recent",[])
            if paths: path = paths[0]
        if path is None: # 无法获取任何最近项 - 退出
            return
        path = os.path.normpath(path)
        if not (os.path.exists(path) and os.path.isfile(path)):
            self.tk.bell()
            mb.showerror("打开{}时发生错误".format(os.path.basename(path)), "路径'{}'不存在。".format(path))
            self.lift_window()
            return
        return self.pre_open_with_path(path)

    def check_open(self, plists = []):
        if self.is_opening: # 已在打开 - 循环直到不打开
            self.tk.after(5, lambda:self.check_open(plists))
            return
        self.is_opening = True
        try:
            plists = [x for x in plists if not self.regexp.search(x)]
            if isinstance(plists, list) and len(plists):
                at_least_one = False
                # 迭代传递的plists并打开它们
                for p in set(plists):
                    window = self.pre_open_with_path(p)
                    if not window: continue
                    at_least_one = True
                    if self.start_window is None:
                        self.start_window = window
                if not at_least_one: # 如果都没有打开，打开一个新的plist
                    windows = self.stackorder(self.tk)
                    if not len(windows):
                        self.start_window = self.new_plist()
            elif not len(self.stackorder(self.tk)):
                # 创建一个新的plist开始
                self.start_window = self.new_plist()
        except Exception as e:
            self.tk.bell()
            mb.showerror("check_open()函数出错",repr(e))
            self.lift_window()
        self.is_opening = False

    def open_plist_from_app(self, *args):
        if self.is_opening: # 已在打开 - 循环直到不打开
            self.tk.after(5, lambda:self.open_plist_from_app(*args))
            return
        self.is_opening = True
        try:
            if isinstance(args, str):
                args = [args]
            args = [x for x in args if not self.regexp.search(x)]
            for arg in args:
                windows = self.stackorder(self.tk)
                # 验证没有其他窗口已选择该文件
                existing_window = next((window for window in windows if not window in self.default_windows and window.current_plist==arg),None)
                if existing_window:
                    self.lift_window(existing_window)
                    existing_window.reload_from_disk(None)
                    continue
                if len(windows) == 1 and windows[0] == self.start_window and windows[0].edited == False and windows[0].current_plist is None:
                    # 新窗口 - 替换内容
                    current_window = windows[0]
                else:
                    current_window = None
                # 加载plist
                window = self.pre_open_with_path(arg,current_window)
                if self.start_window is None: self.start_window = window
        except Exception as e:
            self.tk.bell()
            mb.showerror("open_plist_from_app()函数出错",repr(e))
            self.lift_window()
        self.is_opening = False

    def change_hd_type(self, value):
        self.hd_type = value

    def reload_from_disk(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # 无事可做
            return
        window = windows[-1] # 获取最后一项(最近的)
        if window in self.default_windows:
            return
        window.reload_from_disk(event)

    def change_data_display(self, new_data = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # 无事可做
            return
        window = windows[-1] # 获取最后一项(最近的)
        if window in self.default_windows:
            return
        window.change_data_display(new_data)

    def oc_clean_snapshot(self, event = None):
        self.oc_snapshot(event,True)

    def oc_snapshot(self, event = None, clean = False):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # 无事可做
            return
        window = windows[-1] # 获取最后一项(最近的)
        if window in self.default_windows:
            return
        window.oc_snapshot(event,clean)

    def hide_show_find(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # 无事可做
            return
        window = windows[-1] # 获取最后一项(最近的)
        if window in self.default_windows:
            return
        window.hide_show_find(event)

    def hide_show_type(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # 无事可做
            return
        window = windows[-1] # 获取最后一项(最近的)
        if window in self.default_windows:
            return
        window.hide_show_type(event)

    def close_window(self, event = None, window = None, check_close = True):
        if window: window.withdraw()
        else:
            # 移除默认窗口
            windows = self.stackorder(self.tk,include_defaults=True)
            if windows: windows[-1].withdraw()
        if check_close: self.check_close()
    
    def check_close(self, lift_last = True):
        windows = self.stackorder(self.tk,include_defaults=True)
        if not windows:
            self.quit()
        elif lift_last:
            self.lift_window(windows[-1])

    def strip_comments(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # 无事可做
            return
        window = windows[-1] # 获取最后一项(最近的)
        if window in self.default_windows:
            return
        window.strip_comments(event)

    def strip_disabled(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # 无事可做
            return
        window = windows[-1] # 获取最后一项(最近的)
        if window in self.default_windows:
            return
        window.strip_disabled(event)

    def strip_whitespace(self, event = None, keys = False, values = False):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # 无事可做
            return
        window = windows[-1] # 获取最后一项(最近的)
        if window in self.default_windows:
            return
        window.strip_whitespace(event,keys=keys,values=values)

    def change_to_type(self, value):
        self.settings["convert_to_type"] = value
        self.convert_values()

    def change_from_type(self, value):
        self.settings["convert_from_type"] = value

    def show_window(self, window, event = None):
        if not window.winfo_viewable():
            # 将窗口居中
            w = window.winfo_width()
            h = window.winfo_height()
            if w==1==h: # 请求宽度，因为尚未绘制
                if window == self.tk: # 使用默认值
                    w, h = 640, 130
                else: # 尝试近似
                    w = window.winfo_reqwidth()
                    h = window.winfo_reqheight()
            x = window.winfo_screenwidth() // 2 - w // 2
            y = window.winfo_screenheight() // 2 - h // 2
            window.geometry("+{}+{}".format(x, y))
            window.deiconify()
        self.lift_window(window)
        if window == self.tk:
            # 仅在显示转换窗口时设置焦点
            self.f_text.focus_set()

    def get_bytes(self, value):
        if sys.version_info >= (3,0) and not isinstance(value,bytes):
            # 转换为字节
            value = value.encode("utf-8")
        return value

    def get_string(self, value):
        if sys.version_info >= (3,0) and not isinstance(value,(str,unicode)):
            # 从字节转换
            value = value.decode("utf-8")
        return value

    def swap_convert(self, event = None):
        # 交换"到"和"从"转换下拉菜单的值
        t,f = self.t_title.get(),self.f_title.get()
        self.settings["convert_to_type"] = f
        self.settings["convert_from_type"] = t
        self.t_title.set(f)
        self.f_title.set(t)
        # 将数据从"到"移动到"从"，并运行转换
        self.f_text.delete(0,tk.END)
        self.f_text.insert(0,self.t_text.get())
        self.convert_values()

    def convert_values(self, event = None):
        from_value = self.f_text.get()
        if not len(from_value):
            # 空 - 无需转换
            return
        # 预先检查十六进制潜在问题
        from_type = self.f_title.get().lower()
        to_type   = self.t_title.get().lower()
        if from_type == "hex":
            if from_value.lower().startswith("0x"):
                from_value = from_value[2:]
            from_value = from_value.replace(" ","").replace("<","").replace(">","")
            if [x for x in from_value if x.lower() not in "0123456789abcdef"]:
                self.tk.bell()
                mb.showerror("无效的十六进制数据","传递的十六进制数据中有无效字符。") # ,parent=self.tk)
                self.lift_window()
                return
        try:
            if from_type in ("decimal","binary"):
                # 转换为十六进制字节
                from_value = "".join(from_value.split()) # 移除空白
                from_value = "{:x}".format(int(from_value,10 if from_type=="decimal" else 2))
                if len(from_value) % 2:
                    from_value = "0"+from_value
            # 处理"从"数据
            if from_type == "base64":
                padded_from = from_value
                from_stripped = from_value.rstrip("=")
                if len(from_stripped) % 4 > 1: # 填充为4的倍数
                    padded_from = from_stripped + "="*(4-len(from_stripped)%4)
                if padded_from != from_value:
                    # 已更改 - 更新"从"框，并设置"从"值
                    from_value = padded_from
                    self.f_text.delete(0,tk.END)
                    self.f_text.insert(0,from_value)
                from_value = base64.b64decode(self.get_bytes(from_value))
            elif from_type in ("hex","decimal","binary"):
                if len(from_value) % 2:
                    # 确保填充十六进制
                    from_value = "0"+from_value
                    # 为所有需要的情况可视化反映
                    if to_type not in ("hex","decimal"):
                        self.f_text.delete(0,tk.END)
                        self.f_text.insert(0,from_value)
                from_value = binascii.unhexlify(self.get_bytes(from_value))
            # 获取转换后的数据
            to_value = self.get_bytes(from_value)
            if to_type == "base64":
                to_value = base64.b64encode(self.get_bytes(from_value))
            elif to_type == "hex":
                to_value = binascii.hexlify(self.get_bytes(from_value))
            elif to_type == "decimal":
                to_value = str(int(binascii.hexlify(self.get_bytes(from_value)),16))
            elif to_type == "binary":
                to_value = "{:b}".format(int(binascii.hexlify(self.get_bytes(from_value)),16))
            if not to_type in ("decimal","binary"):
                to_value = self.get_string(to_value)
            if to_type == "hex":
                # 大写并用空格填充
                to_value = " ".join((to_value[0+i:8+i] for i in range(0, len(to_value), 8))).upper()
            # 设置文本框
            self.t_text.configure(state='normal')
            self.t_text.delete(0,tk.END)
            self.t_text.insert(0,to_value)
            self.t_text.configure(state='readonly')
        except Exception as e:
            # 清除文本框
            self.t_text.configure(state='normal')
            self.t_text.delete(0,tk.END)
            self.t_text.configure(state='readonly')
            self.tk.bell()
            mb.showerror("转换错误",str(e)) # ,parent=self.tk)
            self.lift_window()

    ###                       ###
    # 保存/加载Plist函数 #
    ###                       ###

    def duplicate_plist(self, event = None):
        if self.creating_window:
            return
        self.creating_window = True
        windows = self.stackorder(self.tk)
        if not len(windows):
            # 无事可做
            self.creating_window = False
            return
        window = windows[-1] # 获取最后一项(最近的)
        if window in self.default_windows:
            self.creating_window = False
            return
        # 确保标题唯一
        title = self._get_unique_title(title="未命名.plist")
        # 从当前窗口获取信息并创建新窗口
        plist_data = window.nodes_to_values()
        new_window = plistwindow.PlistWindow(self, self.tk)
        # 确保窗口标题栏颜色更新
        if os.name == "nt": self.set_win_titlebar(windows=new_window)
        # 确保我们复制的plist和数据类型被反映
        new_window.plist_type_string.set(window.plist_type_string.get())
        new_window.data_type_string.set(window.data_type_string.get())
        new_window.int_type_string.set(window.int_type_string.get())
        new_window.bool_type_string.set(window.bool_type_string.get())
        # 用plist数据填充新窗口 - 确保它被"编辑"
        new_window.open_plist(
            None,
            plist_data,
            auto_expand=self.settings.get("expand_all_items_on_open",True),
            title=title
        )
        # 更新"打开最近"菜单
        if str(sys.platform) != "darwin": self.update_recents_for_target(new_window)
        self.lift_window(new_window)
        self.creating_window = False

    def save_plist(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # 无事可做
            return
        window = windows[-1] # 获取最后一项(最近的)
        if window in self.default_windows:
            return
        if window.save_plist(event):
            # 正确保存，确保路径保存在最近项中
            self.add_recent(window.current_plist)
            self.lift_window(window)
    
    def save_plist_as(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # 无事可做
            return
        window = windows[-1] # 获取最后一项(最近的)
        if window in self.default_windows:
            return
        if window.save_plist_as(event):
            # 正确保存，确保路径保存在最近项中
            self.add_recent(window.current_plist)
            self.lift_window(window)

    def undo(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # 无事可做
            return
        window = windows[-1] # 获取最后一项(最近的)
        if window in self.default_windows:
            return
        window.reundo(event)

    def redo(self, event = None):
        windows = self.stackorder(self.tk)
        if not len(windows):
            # 无事可做
            return
        window = windows[-1] # 获取最后一项(最近的)
        if window in self.default_windows:
            return
        window.reundo(event,False)

    def _get_unique_title(self, title="未命名.plist", suffix=""):
        # 尝试创建唯一名称(如果使用未命名.plist，添加数字)
        if "." in title:
            # 考虑扩展名 - 保留前导点
            final_title = ".".join(title.split(".")[:-1])
            ext = "."+title.split(".")[-1]
        else:
            # 无扩展名 - 按原样使用标题
            final_title = title
            ext = ""
        titles = set([x.title().lower() for x in self.stackorder(self.tk)])
        number = 0
        while True:
            temp = "{}{}{}{}".format(
                final_title,
                suffix,
                "" if number == 0 else "-"+str(number),
                ext)
            temp_edit = temp + " - 已编辑"
            temp_lower,temp_edit_lower = temp.lower(),temp_edit.lower()
            if not any((x in titles for x in (temp_lower,temp_edit_lower))):
                final_title = temp
                break
            number += 1
        return final_title
    
    def new_plist(self, event = None):
        if self.creating_window:
            return
        self.creating_window = True
        # 创建新的plistwindow对象
        title = self._get_unique_title(title="未命名.plist")
        window = plistwindow.PlistWindow(self, self.tk)
        # 更新"打开最近"菜单
        if str(sys.platform) != "darwin": self.update_recents_for_target(window)
        # 确保窗口标题栏颜色更新
        if os.name == "nt": self.set_win_titlebar(windows=window)
        # 确保我们的默认plist和数据类型被反映
        window.plist_type_string.set(self.plist_type_string.get())
        window.data_type_string.set(self.data_type_string.get())
        window.int_type_string.set(self.int_type_string.get())
        window.bool_type_string.set(self.bool_type_string.get())
        window.open_plist(title,{}) # 创建空根
        window.current_plist = None # 确保初始化为新
        self.lift_window(window)
        self.creating_window = False
        return window

    def open_plist(self, event=None):
        # 提示用户打开plist，尝试加载它，如果成功，设置其路径为current_plist值
        path = fd.askopenfilename(title = "选择plist文件") # ,parent=current_window) # 显然在10.15上父级会破坏?
        if not len(path):
            # 提升最后聚焦的窗口
            self.lift_window()
            return # 用户取消 - 退出
        path = os.path.abspath(os.path.expanduser(path))
        return self.pre_open_with_path(path)

    def pre_open_with_path(self, path, current_window = None):
        if not path: return # 嗯...不应该发生，但以防万一
        path = os.path.abspath(os.path.expanduser(path))
        windows = self.stackorder(self.tk)
        if current_window is None and len(windows) == 1 and windows[0] == self.start_window and windows[0].edited == False and windows[0].current_plist is None:
            # 新窗口 - 替换内容
            current_window = windows[0]
        # 验证没有其他窗口已选择该文件
        for window in windows[::-1]:
            if window in self.default_windows: continue
            if window.current_plist == path:
                # 找到一个 - 只需提升它并从磁盘重新加载
                self.lift_window(window)
                window.reload_from_disk(None)
                return
        return self.open_plist_with_path(None,path,current_window)

    def open_plist_with_path(self, event = None, path = None, current_window = None):
        if not path: return # 什么?
        path = os.path.abspath(os.path.expanduser(path))
        # 尝试加载plist
        try:
            with open(path,"rb") as f:
                plist_type = "Binary" if plist._is_binary(f) else "XML"
                plist_data = plist.load(f,dict_type=dict if self.settings.get("sort_dict",False) else OrderedDict)
        except Exception as e:
            # 有问题，显示框
            self.tk.bell()
            mb.showerror("打开{}时发生错误".format(os.path.basename(path)), str(e)) # ,parent=current_window)
            self.lift_window()
            return
        # 正确打开 - 加载它并设置我们的值
        if not current_window:
            # 需要先创建一个
            current_window = plistwindow.PlistWindow(self, self.tk)
        # 确保窗口标题栏颜色更新
        if os.name == "nt": self.set_win_titlebar(windows=current_window)
        # 确保我们的默认数据类型被反映
        current_window.data_type_string.set(self.data_type_string.get())
        current_window.int_type_string.set(self.int_type_string.get())
        current_window.bool_type_string.set(self.bool_type_string.get())
        current_window.open_plist(
            path,
            plist_data,
            plist_type=plist_type,
            auto_expand=self.settings.get("expand_all_items_on_open",True)
        )
        self.lift_window(current_window)
        # 添加到"打开最近"列表
        self.add_recent(path)
        return current_window

    def stackorder(self, root = None, include_defaults = False):
        """返回堆叠顺序中的根窗口和顶层窗口列表(最顶层是最后一个)"""
        root = root or self.tk
        check_types = (tk.Toplevel,tk.Tk) if include_defaults else plistwindow.PlistWindow
        c = root.children
        s = root.tk.eval('wm stackorder {}'.format(root))
        L = [x.lstrip('.') for x in s.split()]
        # 移除不需要的小部件
        w = {}
        for x in list(c):
            if isinstance(c.get(x),check_types):
                w[x] = c[x] # 保留有效类型
        if "" in L and isinstance(root,check_types):
            # 我们还需要追加根
            w[""] = root
        # 构建仅包含遵循堆叠顺序的tkinter类的列表
        stack_order = [w[x] for x in L if x in w]
        # 添加任何缺失的窗口(可能最小化)
        stack_order = [x for x in w.values() if not x in stack_order] + stack_order
        # 返回列表，省略任何被withdrawn的窗口
        return [x for x in stack_order if x.wm_state() != "withdrawn"]

    def lift_window(self, window=None, deiconify=False):
        if window is None:
            windows = self.stackorder(self.tk,include_defaults=True)
            if windows: # 获取我们看到的最后一个窗口
                window = windows[-1]
        if window is None: return # 堆叠顺序中无窗口?
        if deiconify and window.state() == "iconic":
            window.deiconify() # 同时提升最小化的窗口
        if sys.platform != "darwin":
            # 对于所有非macOS平台，提升窗口
            # 无论是否取消最小化。在macOS上不要提升
            # 因为它会取消最小化窗口。
            window.lift()
        window.focus_force()
        try: window._tree.focus_force()
        except: pass
        window.attributes("-topmost",True)
        self.tk.after_idle(window.attributes,"-topmost",False)

    def quit(self, event_or_signum=None, frame=None):
        if self.is_quitting: return # 已在退出 - 不要尝试同时做两次
        self.is_quitting = True # 锁定为一次退出尝试
        if isinstance(event_or_signum,int) and frame is not None:
            print("捕获到KeyboardInterrupt - 清理中...")
        # 获取所有有未保存更改的窗口列表
        unsaved = [x for x in self.stackorder(self.tk) if x.edited]
        ask_to_save = True
        if len(unsaved) > 1: # 请求审阅
            answer = mb.askyesnocancel(
                "未保存的更改",
                "您有{:,}个文档{}未保存更改。\n要审阅吗?\n(如果您不审阅，所有未保存的更改将丢失)".format(
                    len(unsaved),
                    "" if len(unsaved)==1 else "个"
                ))
            if answer is None:
                # 解锁退出并返回 - 用户取消
                self.is_quitting = False
                self.lift_window()
                return
            ask_to_save = answer # 迭代窗口并按需询问保存
        # 遍历窗口并关闭它们 - 按需审阅更改
        if ask_to_save:
            for window in self.stackorder(self.tk)[::-1]:
                if window in self.default_windows or not window.edited:
                    continue
                self.lift_window(window,deiconify=True)
                if not window.close_window(check_saving=ask_to_save,check_close=False):
                    self.is_quitting = False # 解锁退出
                    return # 用户取消或我们未能保存，退出
        # 确保保留任何非事件更新的设置
        prefix = self.comment_prefix_text.get()
        prefix = "#" if not prefix else prefix
        self.settings["comment_strip_prefix"] = prefix
        try:
            max_undo = int(self.undo_max_text.get())
            assert max_undo >= 0
        except:
            max_undo = self.max_undo
        self.settings["max_undo"] = max_undo
        # 实际退出tkinter会话
        self.tk.destroy()
        # 尝试保存设置
        cwd = os.getcwd()
        os.chdir(os.path.abspath(os.path.dirname(__file__)))
        try:
            json.dump(self.settings,open("Scripts/settings.json","w"),indent=4)
        except:
            pass
        os.chdir(cwd)

if __name__ == '__main__':
    plists = []
    if len(sys.argv) > 1:
        plists = sys.argv[1:]
    p = ProperTree(plists)