import json
import os
import re
import sys

from flask import Flask, send_from_directory, abort, render_template, Response, request, redirect, url_for

from mdict_dir import Dir

# IndexBuilder('vocab.mdx')
# pass
app = Flask(__name__)

# add reg support
from werkzeug.routing import BaseConverter


class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]


app.url_map.converters['regex'] = RegexConverter


#################
# 将多层路径整合为文件名
def path2file(path):
    return path.replace('/', '_')


# 将词典名转为用于url的形式
def title2url(title):
    return re.sub(r"。|，|？|\s|,|\.|/|\\|(|)|（|）", "", title)


@app.route('/')
def hello_world():
    title_url = title2url(mdict._config['dicts'][2]['title'])
    dict_hello_url = f"/dict/{title_url}/hello"
    return redirect(dict_hello_url)


@app.route('/search_all')
def search_all_dicts():
    if len(mdx_map) == 0:
        return "There is no dicts, please check your configuration."
    return render_template("search_all.html", subpages=None)


@app.route('/search_all/<word>')
def search_all_dicts_with_word(word):
    if len(mdx_map) == 0:
        return "There is no dicts, please check your configuration."
    url_titles = [title2url(x['title']) for x in mdict._config['dicts']]
    # get all rendered templates
    rendered_templates = [getEntry(title, word) for title in url_titles]

    return render_template("search_all.html", subpages=rendered_templates, word=word)


@app.route('/search_all/<regex(".+?\."):base><regex("css|png|jpg|gif|mp3|js|wav|ogg"):ext>')
def getFileFromAll(base, ext):
    # print(base + ext, file=sys.stderr)
    mdd_key = '\\{0}{1}'.format(base, ext).replace("/", "\\")
    the_builder = None
    for title, builder in mdx_map.items():
        if builder.mdd_lookup(mdd_key):
            the_builder = builder
    if the_builder == None:
        return "没有找到此词典"

    # 是否是mdd内的文件
    cache_name = path2file(base + ext)
    cache_full = os.path.join(mdd_cache_dir, cache_name)
    if not os.path.isfile(cache_full):
        mdd_key = '\\{0}{1}'.format(base, ext).replace("/", "\\")
        byte = the_builder.mdd_lookup(mdd_key)
        if not byte:  # 在 mdd 内未找到指定文件
            abort(404)  # 返回 404
        file = open(cache_full, 'wb')
        file.write(byte[0])
        file.close()
    return send_from_directory(mdd_cache_dir, cache_name)


@app.route('/dict/')
def all_dicts():
    dicts = []
    for dic in mdict._config['dicts']:
        title = dic['title']
        dicts.append({
            'title': title,
            'description': dic['description'],
            'path': dic['mdx_name'],
            'url': f'/dict/{title2url(title)}/hello'
        })
    return render_template('dicts.html', dicts=dicts)


@app.route('/dict/<title>/')
def description(title):
    dict_hello_url = f"/dict/{title}/hello"
    return redirect(dict_hello_url)


@app.route('/dict/search/<query>/')
def search(query):
    result = []
    for xxx in mdict._config['dicts']:
        bd = xxx['builder']
        result.append([title2url(xxx['title']), bd.get_mdx_keys(query)])
    dat = json.dumps(result, ensure_ascii=False)
    resp = Response(response=dat,  # standard way to return json
                    status=200,
                    mimetype="application/json")
    return (resp)


@app.route('/dict/<title>/<regex(".+?\."):base><regex("css|png|jpg|gif|mp3|js|wav|ogg"):ext>')
def getFile(title, base, ext):
    # print(base + ext, file=sys.stderr)
    if title not in mdx_map:
        return "没有找到此词典"
    builder = mdx_map[title]
    # 是否为外挂文件
    external_file = os.path.join(mdict_dir, base + ext)
    if os.path.isfile(external_file):
        return send_from_directory(mdict_dir, base + ext)

    # 是否是mdd内的文件
    cache_name = path2file(base + ext)
    cache_full = os.path.join(mdd_cache_dir, cache_name)
    if not os.path.isfile(cache_full):
        mdd_key = '\\{0}{1}'.format(base, ext).replace("/", "\\")
        byte = builder.mdd_lookup(mdd_key)
        if not byte:  # 在 mdd 内未找到指定文件
            abort(404)  # 返回 404
        file = open(cache_full, 'wb')
        file.write(byte[0])
        file.close()
    return send_from_directory(mdd_cache_dir, cache_name)


@app.route('/dict/<title>/<hwd>')
def getEntry(title, hwd):
    if title not in mdx_map:
        return "没有找到此词典"
    builder = mdx_map[title]
    result = builder.mdx_lookup(hwd)
    if result:
        text = result[0]
    else:
        text = "<p>在词典{0}中没有找到{1}</p>".format(title, hwd)

    dicts = []
    for dic in mdict._config['dicts'][:3]:
        t = dic['title']
        dicts.append({
            'title': t,
            'url': f'/dict/{title2url(t)}/{hwd}'
        })
    url_titles = [title2url(x['title']) for x in mdict._config['dicts']][:3]  # limited to first 3

    # return
    # text.replace("\r\n","").replace("entry://","").replace("sound://","")
    return render_template("entry.html", content=text, title=title, entry=hwd, dicts=dicts)


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        folder_path = request.form['folder_path']
        # Do something with the selected folder path, such as saving it in a database or configuration file
        return render_template('settings.html', folder_path=folder_path)
    else:
        return render_template('settings.html')


# handles 404
# @app.errorhandler(404)
# def handle_404(e):
#     # handle all other routes here
#     print("This is not found", request.url)
#     return 'Not Found, but we HANDLED IT'

if __name__ == '__main__':
    # init app, take the last parameter as dict path
    mdict_dir = sys.argv[-1]
    mdd_cache_dir = 'cache'

    print(f"looking into folder {mdict_dir}")
    print(os.listdir(mdict_dir))

    if not os.path.isdir(mdict_dir):
        print('no mdx directory\n', file=sys.stderr)
        os.makedirs(mdict_dir)

    if not os.path.isdir(mdd_cache_dir):
        os.makedirs(mdd_cache_dir)

    mdict = Dir(mdict_dir)
    # config = mdict._config['dicts'][0]
    mdx_map = {}
    for dic in mdict._config['dicts']:
        mdx_map[title2url(dic['title'])] = dic['builder']

    app.run('0.0.0.0', 5000, debug=True)
