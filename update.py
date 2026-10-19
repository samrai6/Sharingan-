from logging import FileHandler, StreamHandler, INFO, basicConfig, error as log_error, info as log_info
from os import path as ospath, environ, remove
from subprocess import run as srun, call as scall
from pkg_resources import working_set
from requests import get as rget
from dotenv import load_dotenv, dotenv_values
from pymongo import MongoClient

if ospath.exists('log.txt'):
    with open('log.txt', 'r+') as f:
        f.truncate(0)

if ospath.exists('rlog.txt'):
    remove('rlog.txt')

basicConfig(format="[%(asctime)s] [%(levelname)s] - %(message)s",
            datefmt="%d-%b-%y %I:%M:%S %p",
            handlers=[FileHandler('log.txt'), StreamHandler()],
            level=INFO)

CONFIG_FILE_URL = environ.get('CONFIG_FILE_URL')
try:
    if len(CONFIG_FILE_URL) == 0:
        raise TypeError
    try:
        res = rget(CONFIG_FILE_URL)
        if res.status_code == 200:
            with open('config.env', 'wb+') as f:
                f.write(res.content)
        else:
            log_error(f"Failed to download config.env {res.status_code}")
    except Exception as e:
        log_error(f"CONFIG_FILE_URL: {e}")
except:
    pass

load_dotenv('config.env', override=True)

try:
    if bool(environ.get('_____REMOVE_THIS_LINE_____')):
        log_error('The README.md file there to be read! Exiting now!')
        exit()
except:
    pass

BOT_TOKEN = environ.get('BOT_TOKEN', '')
if len(BOT_TOKEN) == 0:
    log_error("BOT_TOKEN variable is missing! Exiting now")
    exit(1)

bot_id = BOT_TOKEN.split(':', 1)[0]

DATABASE_URL = environ.get('DATABASE_URL', '')
if len(DATABASE_URL) == 0:
    DATABASE_URL = None

if DATABASE_URL is not None:
    conn = MongoClient(DATABASE_URL)
    db = conn.kpsmlx
    old_config = db.settings.deployConfig.find_one({'_id': bot_id})
    config_dict = db.settings.config.find_one({'_id': bot_id})
    if old_config is not None:
        del old_config['_id']
    if (old_config is not None and old_config == dict(dotenv_values('config.env')) or old_config is None) \
            and config_dict is not None:
        environ['UPSTREAM_REPO'] = config_dict['UPSTREAM_REPO']
        environ['UPSTREAM_BRANCH'] = config_dict['UPSTREAM_BRANCH']
        environ['UPGRADE_PACKAGES'] = config_dict.get('UPDATE_PACKAGES', 'False')
    conn.close()

UPGRADE_PACKAGES = environ.get('UPGRADE_PACKAGES', 'False') 
if UPGRADE_PACKAGES.lower() == 'true':
    packages = [dist.project_name for dist in working_set]
    scall("uv pip install --system " + ' '.join(packages), shell=True)

UPSTREAM_REPO = environ.get('UPSTREAM_REPO', '')
if len(UPSTREAM_REPO) == 0:
    UPSTREAM_REPO = "https://github.com/Tamilupdates/KPSML-X"

UPSTREAM_BRANCH = environ.get('UPSTREAM_BRANCH', '')
if len(UPSTREAM_BRANCH) == 0:
    UPSTREAM_BRANCH = 'kpsmlx'

if UPSTREAM_REPO is not None:
    if ospath.exists('.git'):
        srun(["rm", "-rf", ".git"], check=True)

    # Run Git commands separately instead of interpolating environment values
    # into a shell command. This preserves updater behavior and avoids shell injection.
    commands = [
        ["git", "init", "-q"],
        ["git", "config", "--global", "user.email", "kpstorrent@gmail.com"],
        ["git", "config", "--global", "user.name", "kpsbots"],
        ["git", "add", "."],
        ["git", "commit", "-sm", "update", "-q"],
        ["git", "remote", "add", "origin", UPSTREAM_REPO],
        ["git", "fetch", "origin", "-q"],
        ["git", "reset", "--hard", f"origin/{UPSTREAM_BRANCH}", "-q"],
    ]

    try:
        for command in commands:
            srun(command, check=True)
        update_succeeded = True
    except Exception as e:
        log_error(f"Updater failed: {e}")
        update_succeeded = False

    repo = UPSTREAM_REPO.rstrip('/').split('/')
    if len(repo) >= 2:
        UPSTREAM_REPO = f"https://github.com/{repo[-2]}/{repo[-1]}"
    if update_succeeded:
        log_info('Successfully updated with latest commits !!')
    else:
        log_error('Something went Wrong ! Retry or Ask Support !')
    log_info(f'UPSTREAM_REPO: {UPSTREAM_REPO} | UPSTREAM_BRANCH: {UPSTREAM_BRANCH}')
