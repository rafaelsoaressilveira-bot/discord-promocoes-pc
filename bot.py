import os

POSTED_FILE = "posted_deals.json"

def load_posted():
if not os.path.exists(POSTED_FILE):
return set()
return set()

def save_posted(posted):
posted_list = list(posted)[-1000:]
print(posted_list)

print("TESTE OK")
save_posted(load_posted())

Aqui é importante: na linha

if not os.path.exists(POSTED_FILE):

existem 4 espaços antes de if.

E em:

posted_list = list(posted)[-1000:]
