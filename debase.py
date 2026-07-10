import base64
b64_str=input("请输入Base64编码字符串：").strip()
try:
    raw=base64.b64decode(b64_str)
    text=raw.decode("utf-8")
    print("\n解码结果：")
    print(text)
except base64.binascii.Error:
    print("错误：输入不是合法的Base64字符串！")
except UnicodeDecodeError:
    print("警告：解码后不是UTF-8文本，原始字节输出：")
    print(raw)