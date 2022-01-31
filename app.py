# -*- coding: utf-8 -*-

"""
My super duper codelookup replacement.
"""

from flask import Flask, redirect, render_template, request, url_for, Markup
import time
import requests
import json
import re

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Language code lookup 1.0 (https://codelookup.toolforge.org/)"
}

def get_language_code(code, state="code"):
    code = code.lower()
    code = code.replace("_", "-")
    if re.fullmatch(r"[a-z]{2,3}(-[a-z0-9]+)*", code) and not re.match(r"^q[a-t][a-z]", code):
        if state == "language":
            remap = {
                "bat-smg": "sgs",
                "fiu-vro": "vro",
                "roa-rup": "rup",
                "zh-classical": "lzh",
                "zh-min-nan": "nan",
                "zh-yue": "yue"
            }
            if code in remap:
                return remap[code]
            else:
                return code.split("-")[0]
        elif state == "sitecode":
            remap = {
                "sgs": "bat-smg",
                "vro": "fiu-vro",
                "rup": "roa-rup",
                "nb": "no",
                "lzh": "zh-classical",
                "nan": "zh-min-nan",
                "yue": "zh-yue"
            }
            if code in remap:
                return remap[code]
            else:
                return code
        else:
            return code
    else:
        return "INVALID"

def get_code_data(lang):
    api = "https://hub.toolforge.org/{}:{}?format=json&lang=en"
    if len(lang) == 2:
        api = api.format("P218", lang)
    else:
        api = api.format("P220", lang)
    req = requests.get(api, headers=HEADERS).json()
    if "destination" in req:
        return req
    else:
        return False

def get_twn_stats(lang):
    api = "https://translatewiki.net/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "meta": "languagestats",
        "lslanguage": lang
    }
    req = requests.get(api, params=params, headers=HEADERS).json()
    if "error" in req and req["error"]["code"] == "translate-invalidlanguage":
        return False
    else:
        return req["query"]["languagestats"]

def get_group_stats(stats, groups):
    ret = {}
    for group in stats:
        if group["group"] in groups:
            total = group["total"]
            translated = group["translated"]
            percentage = int(translated) / int(total) * 100
            ret[group["group"]] = {
                "translated": translated,
                "total": total,
                "percentage": round(percentage, 2)
            }
    return ret

def get_mediawiki_languages(code):
    api = "https://meta.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "meta": "siteinfo",
        "siprop": "languages"
    }
    req = requests.get(api, params=params, headers=HEADERS).json()["query"]["languages"]
    match = False
    for entry in req:
        if entry["code"] == code:
            match = True
            break
    return match
    
def get_wikidata_languages(code):
    api = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "meta": "wbcontentlanguages"
    }
    req = requests.get(api, params=params, headers=HEADERS).json()["query"]["wbcontentlanguages"]
    if code in req:
        return True
    else:
        return False

def get_wikimedia_sites(code):
    api = "https://meta.wikimedia.org/w/api.php"
    params = {
        "action": "sitematrix",
        "format": "json",
        "smtype": "language",
        "smlimit": 5000
    }
    req = requests.get(api, params=params, headers=HEADERS).json()["sitematrix"]
    match = False
    for entry in req:
        if entry == "count":
            continue
        else:
            if req[entry]["code"] == code:
                match = req[entry]
                break
    if match:
        ret = {}
        for site in match["site"]:
            if "closed" in site:
                continue
            else:
                ret[site["code"]] = site["sitename"]
        return ret
    else:
        return False

def get_everything(langcode):
    code = get_language_code(langcode)
    lang = get_language_code(langcode, "language")
    sitecode = get_language_code(langcode, "sitecode")
    res = {
        "cachetime": time.time(),
        "code": code,
        "lang": lang,
        "languagename": "<i>(unknown)</i>",
        "sitecode": sitecode,
        "wellformed": False,
        "actual": False,
        "twn-enabled": False,
        "mw-enabled": False,
        "wd-enabled": False,
        "wm-sites": {
            "wiki": False,
            "wiktionary": False,
            "wikibooks": False,
            "wikinews": False,
            "wikiquote": False,
            "wikisource": False,
            "wikiversity": False,
            "wikivoyage": False
        },
        "groupstats": {}
    }
    
    if code != "INVALID":
        res["wellformed"] = True
    else:
        return res
    
    if get_code_data(lang):
        res["actual"] = get_code_data(lang)["origin"]["qid"]
        try:
            res["languagename"] = get_code_data(lang)["destination"]["preferedSitelink"]["title"]
        except:
            pass
    
    twnstats = get_twn_stats(code)
    groups_to_find = ["core-0-mostused", "core", "ext-proofreadpage-user", "ext-collection-user", "wikimedia-main", "out-wikimedia-mobile-wikipedia-android-strings", "out-wikimedia-mobile-wikipedia-ios"]
    
    if twnstats:
        res["twn-enabled"] = True
        res["groupstats"] = get_group_stats(twnstats, groups_to_find)
    
    if get_mediawiki_languages(code):
        res["mw-enabled"] = True
        res["wd-enabled"] = True
    else:
        res["wd-enabled"] = get_wikidata_languages(code)
    
    wmsites = get_wikimedia_sites(sitecode)
    if wmsites:
        res["wm-sites"].update(wmsites)
    
    return res

def encapsulate_p(x):
    if x[0] == "<":
        return x
    else:
        return "<p>" + x + "</p>"

def statblurb(code, stats, group, displaystats=True):
    groupnames = {
        "core-0-mostused": "Most important messages",
        "core": "MediaWiki core messages",
        "ext-collection-user": "Collection extension",
        "ext-proofreadpage-user": "ProofreadPage extension",
        "wikimedia-main": "Main extensions used by Wikimedia",
        "out-wikimedia-mobile-wikipedia-android-strings": "Android Wikipedia app",
        "out-wikimedia-mobile-wikipedia-ios": "iOS Wikipedia app"
    }
    svg = """<svg class="progress-ring" height="30" width="30" data-percentage="{0}">
    <linearGradient id="{1}" gradientTransform="rotate(45)">
        <stop offset="0%" stop-color="#2a4b8d" />
        <stop offset="100%" stop-color="#36c" />
    </linearGradient>
    <circle class="progress-ring__bg" stroke-width="3" fill="transparent" r="8" cx="15" cy="15" stroke="#ddd" />
    <circle class="progress-ring__circle" stroke-width="5" fill="transparent" r="8" cx="15" cy="15" stroke="url('#{1}')" stroke-dasharray="50.265" stroke-dashoffset="50.265" />
    </svg>""".format(stats["percentage"], "stat-" + group)
    locstats = ""
    if displaystats:
        locstats = "<span class='statlink'>{0} <a href='https://translatewiki.net/wiki/Special:Translate?language={1}&group={2}'>{6}</a>: {3}&nbsp;%: {4} / {5} messages</span>"
    else:
        locstats = "<span class='statlink'>{0} <a href='https://translatewiki.net/wiki/Special:Translate?language={1}&group={2}' title='{3} %: {4} / {5} messages'>{6}</a></span>"
    
    return locstats.format(
        svg,
        code,
        group,
        stats["percentage"],
        stats["translated"],
        stats["total"],
        groupnames[group]
    )

def build_content(langcode):
    results = get_everything(langcode)
    content = []
    infobutton = "<img src='https://upload.wikimedia.org/wikipedia/commons/6/69/OOjs_UI_icon_help.svg' class='infobutton' data-target='{}'>"
    infobox = "<aside id='infobox-{}'>{}</aside>"
    svg = """<svg class="progress-ring" height="30" width="30" data-percentage="{0}">
    <linearGradient id="{1}" gradientTransform="rotate(45)">
        <stop offset="0%" stop-color="#2a4b8d" />
        <stop offset="100%" stop-color="#36c" />
    </linearGradient>
    <circle class="progress-ring__bg" stroke-width="3" fill="transparent" r="8" cx="15" cy="15" stroke="#ddd" />
    <circle class="progress-ring__circle" stroke-width="5" fill="transparent" r="8" cx="15" cy="15" stroke="url('#{1}')" stroke-dasharray="50.265" stroke-dashoffset="50.265" />
    </svg>"""
    
    locstats = "<span class='statlink'>{0} <a href='https://translatewiki.net/wiki/Special:Translate?language={1}&group={2}' title='{3} %: {4} / {5} messages'>{6}</a></span>"
    
    if len(langcode) == 0:
        return ""
    if not results["wellformed"]:
        content.append("❌ <code>{}</code> is not a well-formed language code.".format(langcode) + infobutton.format("wellformed"))
        content.append(infobox.format("wellformed", "A well-formed language code conists of 2 letters (ISO 639-1) or three letters (ISO 639-3), and optionally has one or more subtags separated by hyphens. The code you entered does not conform to this."))
        return Markup("\n".join(content))
    else:
        verifybox = "<div id='verifybox'>\nVerify this language code:\n<ul>\n"
        if len(results["lang"]) == 3:
            verifybox += "<li><a href='https://iso639-3.sil.org/code/{0}'>SIL (ISO 639-3 RA)</a></li>\n".format(results["lang"])
        if results["actual"]:
            verifybox += "<li><a href='https://hub.toolforge.org/{}?property=P1394'>Glottolog</a></li>\n".format(results["actual"])
            verifybox += "<li><a href='https://www.wikidata.org/entity/{}'>Wikidata</a></li>\n".format(results["actual"])
        verifybox += "<li><a href='https://r12a.github.io/app-subtags/?check={}'>BCP47 subtag lookup</a></li>".format(results["code"])
        verifybox += "</ul>\n</div>\n"
        content.append(verifybox)
        content.append("✔️ <code>{}</code> is a well-formed language code.".format(langcode) + infobutton.format("wellformed"))
        content.append(infobox.format("wellformed", "A well-formed language code consists of 2 letters (ISO 639-1) or three letters (ISO 639-3), and optionally has one or more subtags separated by hyphens. The code you entered conforms to this, but that doesn't necessarily mean that it is a <i>valid</i> language code."))
    if results["actual"]:
        content.append("✔️ This seems to be a code for an actual language.")
        content.insert(0, "<div class='langname'><code>{0}</code>: {1}</div>".format(results["lang"], results["languagename"]))
    else:
        content.append("❌ This doesn't seem to be an actual language code." + infobutton.format("actual"))
        content.append(infobox.format("actual", "This means that there is currently no item on Wikidata with this language code. Since there could be shortcomings in the data on Wikidata, please verify the language code with the SIL link on the right."))
    if results["twn-enabled"]:
        content.append("✔️ This language code is enabled <a href='https://translatewiki.net/wiki/Portal:{}'>on Translatewiki</a>.".format(langcode))
        statbox = "<div class='groupstatbox'>\n"
        for group in results["groupstats"]:
            statbox += statblurb(results["code"], results["groupstats"][group], group) + "<br>\n"
        statbox += "</div>"
        content.append(statbox)
    else:
        content.append("❌ This language code is not enabled on Translatewiki." + infobutton.format("twnenabled"))
        content.append(infobox.format("twnenabled", "In order to enable a language for translation on Translatewiki, you need to request that it be added on <a href='https://translatewiki.net/wiki/Support'>the Support page</a>. Translatewiki is independent of Wikimedia wikis, so you may need to <a href='https://translatewiki.net/'>register an account</a> there first.<br><br>Please only request a language if you know it well and intend to translate into it."))
    if results["mw-enabled"]:
        content.append("✔️ This language code is available for general use in MediaWiki.")
    else:
        content.append("❌ This language is not yet available for general use in MediaWiki." + infobutton.format("mwenabled"))
        content.append(infobox.format("mwenabled", "The best way to make a language code available for general use in MediaWiki is to complete the <a href='https://translatewiki.net/wiki/Special:Translate?language={}&group=core-0-mostused'>translation of the most important messages</a> into that language.".format(results["code"])))
    if results["wd-enabled"]:
        content.append("✔️ This language is available for general use on Wikidata.")
    else:
        content.append("❌ This language is not yet available for general use on Wikidata." + infobutton.format("wdenabled"))
        content.append(infobox.format("wdenabled", "The best way to enable a language code for Wikidata is the same as for MediaWiki: <a href='https://translatewiki.net/wiki/Special:Translate?language={}&group=core-0-mostused'>Translate the most important messages</a> into that language. However, if you are not able to do that for some reason, but the language code is still needed in Wikidata, you can see the appropriate steps to take on <a href='https://www.wikidata.org/wiki/Special:MyLanguage/Help:Monolingual_text_languages'>Help:Monolingual text languages</a>.".format(results["code"])))
        
    tablestart = "<table class='table'>\n<thead>\n<tr>\n<th>Project</th>\n<th>Localization status</th>\n</tr>\n</thead>\n<tbody>\n"
    tablerows = []
    tablerow = "<tr>\n<td class='row-project row-{}'>{}</td>\n<td>{}</td></tr>\n"
    incubator = "https://incubator.wikimedia.org/wiki/"
    projectmatrix = {
        "wiki": ["Wikipedia", "https://{}.wikipedia.org/", incubator + "Wp/{}"],
        "wiktionary": ["Wiktionary", "https://{}.wiktionary.org/", incubator + "Wt/{}"],
        "wikibooks": ["Wikibooks", "https://{}.wikibooks.org/", incubator + "Wb/{}"],
        "wikinews": ["Wikinews", "https://{}.wikinews.org/", incubator + "Wn/{}"],
        "wikiquote": ["Wikiquote", "https://{}.wikiquote.org/", incubator + "Wq/{}"],
        "wikisource": ["Wikisource", "https://{}.wikisource.org/", "https://wikisource.org/wiki/Main_Page/{}"],
        "wikiversity": ["Wikiversity", "https://{}.wikiversity.org/", "https://beta.wikiversity.org/wiki/"],
        "wikivoyage": ["Wikivoyage", "https://{}.wikivoyage.org/", incubator + "Wy/{}"]
    }
    
    for project in results["wm-sites"]:
        col2 = ""
        if len(results["groupstats"]) == 0:
            col2 = "<i>The language is not enabled in Translatewiki.</i>"
        else:
            col2 = statblurb(results["code"], results["groupstats"]["core-0-mostused"], "core-0-mostused", False)
            col2 += statblurb(results["code"], results["groupstats"]["core"], "core", False)
            if project == "wikibooks" or project == "wikisource":
                col2 += statblurb(results["code"], results["groupstats"]["ext-collection-user"], "ext-collection-user", False)
            if project == "wikisource":
                col2 += statblurb(results["code"], results["groupstats"]["ext-proofreadpage-user"], "ext-proofreadpage-user", False)
        if results["wm-sites"][project]:
            tablerows.append(tablerow.format(project, "<a href='" + projectmatrix[project][1].format(results["sitecode"]) + "'>" + results["wm-sites"][project] + "</a>", col2))
        else:
            tablerows.append(tablerow.format(project, projectmatrix[project][0] + " (<a href='" + projectmatrix[project][2].format(results["code"]) + "'>Incubator</a>)", col2))
    tableend = "</table>\n"
    
    content.append(tablestart + "".join(tablerows) + tableend)
    content = map(encapsulate_p, content)
    return Markup("\n".join(content))

@app.route("/", methods=["GET", "POST"], defaults={"path": ""})
@app.route("/<path>", methods=["GET", "POST"])
def index(path):
    if path == '' and 'langcode' in request.args:
        return redirect(url_for('index', path=request.args['langcode']))
    path = path[:20]
    return render_template("index.html", langcode=path, content=build_content(path))