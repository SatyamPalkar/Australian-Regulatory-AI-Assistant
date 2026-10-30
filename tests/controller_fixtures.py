import json


def route(intent, relation="new", retailer="none", mention="", reason=""):
    return json.dumps(dict(intent=intent, relation=relation, retailer=retailer, mention=mention, reason=reason))
