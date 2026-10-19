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
    # into shell commands.
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
        bot_init = ospath.join('bot', '__init__.py')
        try:
            with open(bot_init, 'r', encoding='utf-8') as f:
                source = f.read()

            changes = []
            if 'workers=1000' in source:
                source = source.replace('workers=1000', 'workers=10', 1)
                changes.append('Pyrogram workers=10')

            test_torrent_line = 'Thread(target=aria2c_init).start()'
            if test_torrent_line in source:
                source = source.replace(
                    test_torrent_line,
                    "log_info('Skipped startup test torrent to reduce memory usage')",
                    1
                )
                changes.append('startup test torrent disabled')

            if '"pool_maxsize": 500' in source:
                source = source.replace('"pool_maxsize": 500', '"pool_maxsize": 25', 1)
                changes.append('qBittorrent HTTP pool_maxsize=25')

            # Respect Telegram's server-provided FloodWait instead of crashing
            # and triggering repeated container restarts during bot authorization.
            import_line = 'from pyrogram import Client as tgClient, enums, utils as pyroutils'
            if import_line in source and 'from pyrogram.errors import FloodWait' not in source:
                source = source.replace(import_line, import_line + '\nfrom pyrogram.errors import FloodWait', 1)

            old_login = """bot = wztgClient('bot', TELEGRAM_API, TELEGRAM_HASH, bot_token=BOT_TOKEN, workers=10,
               parse_mode=enums.ParseMode.HTML).start()"""
            new_login = """def start_bot_with_floodwait(client):
    while True:
        try:
            return client.start()
        except FloodWait as e:
            wait_seconds = int(getattr(e, 'value', 444)) + 5
            log_warning(f'Telegram bot login FloodWait; waiting {wait_seconds} seconds before retrying')
            sleep(wait_seconds)


bot = start_bot_with_floodwait(
    wztgClient('bot', TELEGRAM_API, TELEGRAM_HASH, bot_token=BOT_TOKEN, workers=10,
               parse_mode=enums.ParseMode.HTML)
)"""
            if old_login in source:
                source = source.replace(old_login, new_login, 1)
                changes.append('Telegram login FloodWait retry')
            elif 'def start_bot_with_floodwait(client):' not in source:
                log_warning('Could not find exact bot login line for FloodWait retry patch')

            if changes:
                with open(bot_init, 'w', encoding='utf-8') as f:
                    f.write(source)
                log_info('Applied startup fixes: ' + '; '.join(changes))
            else:
                log_info('Startup fixes already applied or source patterns not found')
        except Exception as e:
            log_error(f'Could not apply startup fixes: {e}')
    else:
        log_error('Something went Wrong ! Retry or Ask Support !')
    log_info(f'UPSTREAM_REPO: {UPSTREAM_REPO} | UPSTREAM_BRANCH: {UPSTREAM_BRANCH}')
