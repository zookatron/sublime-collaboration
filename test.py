import infinote

editor = infinote.InfinoteEditor()
editor._state = infinote.State(infinote.Buffer([
	infinote.Segment(1, u'import string, itertools, urllib2, pickle, os, PIL.Image, bz2\r\rprint(pow(2, 38))\r\r# print(open("1.txt").read().translate("".maketrans(dict((chr(x), chr(97+(x-95)%26)) for x in range(97, 123)))))\r\r# print("".join(x for x in open("2.txt").read() if ord(x) > 96 and ord(x) < 123))\r\r# data = open("3.txt").read()\r# print("".join(map(lambda x: data[x], (x+4 for x in range(len(data)-6) if data[x] in string.ascii_lowercase and data[x+1] in string.ascii_uppercase and data[x+2] in string.ascii_uppercase and data[x+3] in string.ascii_uppercase and data[x+4] in string.ascii_lowercase and data[x+5] in string.ascii_uppercase and data[x+6] in string.ascii_uppercase and data[x+7] in string.ascii_uppercase and data[x+8] in string.ascii_lowercase))))\r\r# derp = "63579"\r# while(derp):\r# \ttext = urllib.request.urlopen("http://www.pythonchallenge.com/pc/def/linkedlist.php?nothing="+derp).read()\r# \tprint(text)\r# \tderp = "".join(chr(x) for x in text if chr(x) in string.digits)\r\r#print("\\n".join("".join("".join(a*b for a,b in x)) for '),
	infinote.Segment(1, u'x in pickle.load(open("4.txt", "rb"))))\r\r# img = PIL.Image.open("oxygen.png")\r# print("".join(chr(img.getpixel((x*7, 45))[0]) for x in range(90)))\r# print("".join(chr(x) for x in [105, 110, 116, 101, 103, 114, 105, 116, 121]))\r\r#print(bz2.BZ2Decompressor().decompress(b\'BZh91AY&SYA\\xaf\\x82\\r\\x00\\x00\\x01\\x01\\x80\\x02\\xc0\\x02\\x00 \\x00!\\x9ah3M\\x07<]\\xc9\\x14\\xe1BA\\x06\\xbe\\x084\'), bz2.BZ2Decompressor().decompress(b\'BZh91AY&SY\\x94$|\\x0e\\x00\\x00\\x00\\x81\\x00\\x03$ \\x00!\\x9ah3M\\x13<]\\xc9\\x14\\xe1BBP\\x91\\xf08\'))\r\r# a = [1, 11, 21, 1211, 111221]\r# def describe(number):\r# \tout = \'\'\r# \tc = number[0]\r# \tn = 0\r# \tfor x in number:\r# \t\tif x != c:\r# \t\t\tout += str(n)+c\r# \t\t\tc = x\r# \t\t\tn = 0\r# \t\tn += 1\r# \treturn out+str(n)+c\r\r# x = "1"\r# for i in range(30):\r# \tx = describe(x)\r# \tprint(len(x))\r\r# img = PIL.Image.open("8.jpg")\r# print(img.format, img.size, img.mode)')
	]))


editor.try_insert([u'1', u'', 62, u'a'])
print editor.get_state()
editor.try_insert([1, '', 16, 'D'])
print editor.get_state()
editor.try_insert([1, '1:1', 33, 'i'])
print editor.get_state()


