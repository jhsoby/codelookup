# -*- coding: utf-8 -*-

import time
import re

from flask import Flask, redirect, render_template, request, url_for
import requests

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
            return remap.get(code, code.partition("-")[0])
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
            return remap.get(code, code)
        else:
            return code
    else:
        return "INVALID"

def get_code_data(lang):
    prop = "P218" if len(lang) == 2 else "P220"

    res = requests.get(
        "https://hub.toolforge.org/{}:{}".format(prop, lang),
        headers=HEADERS,
        params={"format": "json", "lang": "en"}
    )
    res.raise_for_status()
    data = res.json()

    if "destination" not in data:
        return None

    return data

def get_twn_stats(lang):
    api = "https://translatewiki.net/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "meta": "languagestats",
        "lslanguage": lang
    }

    res = requests.get(api, params=params, headers=HEADERS)
    data = res.json()
    errorCode = data.get("error", {}).get("code")
    if errorCode == "translate-invalidlanguage":
        return None
    return data["query"]["languagestats"]

def get_group_stats(stats, groups):
    ret = {}
    for group in stats:
        _group = group["group"]
        if _group in groups:
            total = group["total"]
            translated = group["translated"]
            percentage = int(translated) / int(total) * 100
            ret[_group] = {
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

    res = requests.get(api, params=params, headers=HEADERS)
    data = res.json()

    languages = data["query"]["languages"]

    return any(entry.get("code") == code for entry in languages)

def get_wikidata_languages(code):
    api = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "meta": "wbcontentlanguages"
    }

    res = requests.get(api, params=params, headers=HEADERS)
    data = res.json()

    wbcontentlanguages = data["query"]["wbcontentlanguages"]

    return code in wbcontentlanguages

def get_wikimedia_sites(code):
    api = "https://meta.wikimedia.org/w/api.php"
    params = {
        "action": "sitematrix",
        "format": "json",
        "smtype": "language",
        "smlimit": 5000
    }

    req = requests.get(api, params=params, headers=HEADERS)
    data = req.json()
    sitematrix = data["sitematrix"]

    match = None
    for entry, val in sitematrix.items():
        if entry == "count":
            continue

        if val.get("code") == code:
            match = val
            break

    if match is None:
        return None

    ret = {}

    for site in match["site"]:
        if "closed" in site:
            continue
        ret[site["code"]] = site["sitename"]

    return ret

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
            "wikiquote": False,
            "wikisource": False,
            "wikiversity": False,
            "wikivoyage": False
        },
        "groupstats": {}
    }

    if code == "INVALID":
        return res

    res["wellformed"] = True

    codeData = get_code_data(lang)

    if codeData:
        res["actual"] = codeData["origin"]["qid"]
        languagename = codeData.get("destination", {}).get("preferedSitelink", {}).get("title")
        if languagename is not None:
            res["languagename"] = languagename

    twnstats = get_twn_stats(code)

    groups_to_find = (
        "core-0-mostused",
        "core",
        "ext-proofreadpage-user",
        "ext-collection-user",
        "wikimedia-main",
        "out-wikimedia-mobile-wikipedia-android-strings",
        "out-wikimedia-mobile-wikipedia-ios"
    )

    if twnstats:
        res["twn-enabled"] = True
        res["groupstats"] = get_group_stats(twnstats, groups_to_find)

    if get_mediawiki_languages(code):
        res["mw-enabled"] = True
        res["wd-enabled"] = True
    else:
        res["wd-enabled"] = get_wikidata_languages(code)

    wmsites = get_wikimedia_sites(sitecode)

    if wmsites is not None:
        res["wm-sites"].update(wmsites)

    return res

@app.route("/", methods=["GET", "POST"], defaults={"path": ""})
@app.route("/<path>", methods=["GET", "POST"])
def index(path):
    langcode = request.args.get('langcode')
    if langcode is not None:
        return redirect(url_for('index', path=langcode))
    langcode = path[:20]
    results = {}
    if len(langcode) != 0:
        results = get_everything(langcode)
    return render_template("index.html", langcode=langcode, results=results)
