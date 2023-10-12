import sys
import fitz
from PIL import Image
from pprint import pprint as pp
import socket
import os
import threading
import schedule

def get_page_count(render_params):
    pdfs = render_params["pdfs"]
    file_index = render_params["file_index"]
    return fitz.open(pdfs[file_index]).page_count

def get_render_params(render_params, data):
    pp("IN")
    pp(render_params)
    cmd = data.decode().strip()
    if cmd == "n":
        render_params["page_index"] += 1
        render_params["page_index"] %= get_page_count(render_params)
    elif cmd == "p":
        render_params["page_index"] -= 1
        render_params["page_index"] %= get_page_count(render_params)
    elif cmd == "Q":
        render_params["quit"] = True
    elif cmd == "N":
        render_params["file_index"] += 1 
        render_params["file_index"] %= len(render_params["pdfs"])
        render_params["page_index"] = 0
    elif cmd == "P":
        render_params["file_index"] -= 1 
        render_params["file_index"] %= len(render_params["pdfs"])
        render_params["page_index"] = 0
    return render_params
    
def create_unix_socket(socket_path):
    try:
        os.unlink(socket_path)
    except OSError:
        if os.path.exists(socket_path):
            raise
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(socket_path)
    server.listen(1)
    return server, socket_path


def draw_bitmap_at(f, x, y, w, h, pixmap):
    for i in range(0, h):
        f.seek(4 * ((y + i) * 1920 + x))
        for j in range(0, w):
            pixel = bytearray(pixmap.getpixel((j, i)))
            pixel[0], pixel[2] = pixel[2], pixel[0]
            f.write(pixel)

def get_fbsize():
    with open("/sys/class/graphics/fb0/virtual_size", "r") as f:
        return tuple(map(int, f.readline().split(",")))

def get_optimal_pdfsize():
    fbwidth, fbheight = get_fbsize()
    return fbwidth // 2, fbheight

def render(render_params):
    pdfs = render_params["pdfs"]
    file_index = render_params["file_index"]
    page_index = render_params["page_index"]
    zoom = render_params["zoom"]
    offset_x = render_params["offset_x"]
    offset_y = render_params["offset_y"]
    width = render_params["width"]
    height = render_params["height"]
    fd = render_params["fd"]
    pdf = fitz.open(pdfs[file_index])
    page = pdf[page_index]
    pix = page.get_pixmap(colorspace=fitz.csRGB, alpha=True, dpi=200)
    im = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
    im = im.resize((width, height))
    draw_bitmap_at(fd, width+offset_x, 0+offset_y, width, height, im)

def render_thread(*args, **kwargs):
    schedule.every(0.1).seconds.do(render, args[0])
    while args[0]["quit"] == False:
        schedule.run_pending()

def server_thread(*args, **kwargs):
    render_params = args[0]
    server, socket_path = create_unix_socket('/tmp/my_fbpdf_server')
    while True:
        connection, client_address = server.accept()
        try:
            data = connection.recv(1024)
            if not data:
                break
            render_params = get_render_params(render_params, data)
            if render_params["quit"]:
                break
        except Exception as e:
            pp(e)
        finally:
            connection.close()
    os.unlink(socket_path)

render_params = {
   "pdfs": sys.argv[1:],
   "file_index": 0,
   "page_index": 0,
   "zoom": 1.0,
   "offset_x": 0,
   "offset_y": 0,
   "width": get_optimal_pdfsize()[0],
   "height": get_optimal_pdfsize()[1],
   "fd": open("/dev/fb0", "wb"),
   "quit": False
}

if __name__ == "__main__":
    th_render = threading.Thread(target=render_thread, args=(render_params,))
    th_render.start()
    th_server = threading.Thread(target=server_thread, args=(render_params,))
    th_server.start()

    th_render.join()
    th_server.join()
    render_params["fd"].close()
