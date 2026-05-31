import discord
import asyncio
import sys
import os
import tty
import termios
import json
import aiohttp

ascii = r"""
 ____  __.                            .__
|    |/ _|___.__._______  ____   ____ |__|__  ___
|      < <   |  |\_  __ \/  _ \ /    \|  \  \/  /
|    |  \ \___  | |  | \(  <_> )   |  \  |>    <
|____|__ \/ ____| |__|   \____/|___|  /__/__/\_ \
        \/\/                        \/         \/
"""

diamond = "\u25c6"


def glowpurple(text):
    return f"\033[38;5;135m{text}\033[0m"


def gold(text):
    return f"\033[38;5;220m{text}\033[0m"


def cyan(text):
    return f"\033[38;5;51m{text}\033[0m"


def header():
    print(glowpurple(ascii))
    print(glowpurple("        ð™¼ðšŠðšðšŽ ðš‹ðš¢ ð™±ðš•ðšŠðš£ðšŽ"))
    print(gold("        Version: 1.0"))
    print()


bar_active = False
bar_pct = 0


def barcolor(pct):
    if pct < 40:
        return "\033[38;5;160m"
    elif pct < 75:
        return "\033[38;5;226m"
    else:
        return "\033[92m"


def renderbar(pct):
    width = 40
    filled = int(width * pct / 100)
    color = barcolor(pct)
    bar = color + "\u2588" * filled + "\033[38;5;238m" + "\u2591" * (width - filled) + "\033[0m"
    sys.stdout.write(f"\r  {bar} {color}{pct}%\033[0m   ")
    sys.stdout.flush()


def erasebar():
    sys.stdout.write("\r\033[2K")
    sys.stdout.flush()


def drawbar(pct):
    global bar_active, bar_pct
    bar_pct = pct
    bar_active = True
    renderbar(pct)


def endbar():
    global bar_active
    erasebar()
    bar_active = False
    print()


def log(msg, kind="success"):
    global bar_active, bar_pct
    if bar_active:
        erasebar()
    if kind == "success":
        print(f"\033[92m{msg}\033[0m")
    elif kind == "info":
        print(cyan(msg))
    elif kind == "warn":
        print(f"\033[38;5;214m{msg}\033[0m")
    elif kind == "fail":
        print(f"\033[38;5;160m{msg}\033[0m")
    elif kind == "debug":
        print(f"\033[38;5;245m[debug] {msg}\033[0m")
    if bar_active:
        renderbar(bar_pct)


def getch():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch2 = sys.stdin.read(1)
            ch3 = sys.stdin.read(1)
            return ch + ch2 + ch3
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def drawmenu(guilds, selected, prompt):
    page = selected // 10
    start = page * 10
    visible = guilds[start:start + 10]
    total_pages = (len(guilds) - 1) // 10 + 1
    os.system("clear")
    header()
    print(f"\033[97m  {prompt}\033[0m\n")
    for i, g in enumerate(visible):
        real = start + i
        if real == selected:
            print(f"  {glowpurple(diamond)} {glowpurple(f'{real+1}. {g.name}')}")
        else:
            print(f"\033[97m    {real+1}. {g.name}\033[0m")
    if total_pages > 1:
        print(f"\n  \033[38;5;245mPage {page+1}/{total_pages} Â· {len(guilds)} servers total\033[0m")
    print(f"\n\033[97m  j/k or up/down to move Â· enter to select\033[0m")


def pickserver(guilds, prompt):
    selected = 0
    while True:
        drawmenu(guilds, selected, prompt)
        key = getch()
        if key in ("k", "\x1b[A"):
            selected = (selected - 1) % len(guilds)
        elif key in ("j", "\x1b[B"):
            selected = (selected + 1) % len(guilds)
        elif key == "\r":
            return guilds[selected]


def hascloningperms(guild):
    me = guild.me
    if me is None:
        return False
    p = me.guild_permissions
    return p.administrator or (p.manage_channels and p.manage_roles)


def loadtoken():
    try:
        with open("config.json") as f:
            return json.load(f)["token"]
    except FileNotFoundError:
        log("config.json not found.", "fail")
        sys.exit(1)
    except KeyError:
        log("No 'token' key found in config.json.", "fail")
        sys.exit(1)


async def fetchbytes(url):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r:
                if r.status == 200:
                    return await r.read()
    except Exception:
        pass
    return None


async def cloneserver(source, target):
    log("Cloning server..", "info")
    targetname = target.name
    channels = list(target.channels)
    existingroles = [r for r in target.roles if not r.managed and not r.is_default()]
    srcroles = sorted([r for r in source.roles if not r.is_default()], key=lambda r: r.position, reverse=True)
    srccats = sorted(source.categories, key=lambda c: c.position)
    srcchannels = sorted(
        [c for c in source.channels if not isinstance(c, discord.CategoryChannel)],
        key=lambda c: (c.category.position if c.category else -1, c.position)
    )
    srcemojis = list(source.emojis)
    srcstickers = list(source.stickers)
    existingemojis = list(target.emojis)
    existingstickers = list(target.stickers)
    total = len(channels) + len(existingroles) + len(existingemojis) + len(existingstickers) + len(srcroles) + len(srccats) + len(srcchannels) + len(srcemojis) + len(srcstickers) + 1
    done = 0

    def tick():
        nonlocal done
        done += 1
        drawbar(int(done / total * 100))

    drawbar(0)
    log("Cloning server info..", "info")
    try:
        icon = await fetchbytes(str(source.icon.url)) if source.icon else None
        await target.edit(name=source.name, description=source.description, icon=icon)
    except discord.Forbidden:
        log("No permission to edit server info", "debug")
    except Exception as e:
        log(f"Failed to clone server info: {e}", "debug")
    tick()

    log("Removing existing channels..", "info")
    async def deletech(ch):
        try:
            await ch.delete()
        except discord.Forbidden:
            log(f"No permission to delete channel: #{ch.name}", "debug")
        except Exception:
            pass
        tick()
    await asyncio.gather(*[deletech(ch) for ch in channels])

    log("Removing existing roles..", "info")
    for r in existingroles:
        try:
            await r.delete()
            await asyncio.sleep(0.3)
        except discord.Forbidden:
            log(f"No permission to delete role: {r.name}", "debug")
        except discord.HTTPException as e:
            if e.status == 429:
                await asyncio.sleep(float(e.response.headers.get("Retry-After", 2)))
                try:
                    await r.delete()
                except Exception:
                    pass
        except Exception:
            pass
        tick()

    log("Cloning roles..", "info")
    rolemap = {}
    rolesfailed = False
    for role in srcroles:
        if rolesfailed:
            tick()
            continue
        for attempt in range(2):
            try:
                nr = await asyncio.wait_for(
                    target.create_role(
                        name=role.name,
                        permissions=role.permissions,
                        colour=role.colour,
                        hoist=role.hoist,
                        mentionable=role.mentionable
                    ),
                    timeout=8
                )
                rolemap[role.id] = nr
                break
            except asyncio.TimeoutError:
                log(f"Timeout creating role {role.name}, skipping role cloning entirely", "debug")
                rolesfailed = True
                break
            except discord.HTTPException as e:
                if e.status == 429:
                    if attempt == 0:
                        log(f"Rate limited on role {role.name}, retrying in 10s..", "debug")
                        await asyncio.sleep(10)
                    else:
                        log(f"Rate limited again on role {role.name}, skipping role cloning", "debug")
                        rolesfailed = True
                        break
                else:
                    log(f"No permission to create role: {role.name}", "debug")
                    break
            except Exception:
                break
        tick()

    if rolesfailed:
        log("Role cloning was skipped or partial â€” channel perms will not be set", "warn")

    if rolemap:
        try:
            myrole = target.me.top_role
            maxpos = myrole.position - 1
            positions = {}
            for rid, nr in rolemap.items():
                srcpos = next(r.position for r in srcroles if r.id == rid)
                positions[nr] = min(max(srcpos, 1), maxpos)
            await target.edit_role_positions(positions)
        except Exception:
            pass

    log("Cloning categories..", "info")
    catmap = {}
    for cat in srccats:
        overwrites = {}
        if not rolesfailed:
            for r, perms in cat.overwrites.items():
                if isinstance(r, discord.Role):
                    mapped = rolemap.get(r.id)
                    if mapped:
                        overwrites[mapped] = perms
                    elif r.is_default():
                        overwrites[target.default_role] = perms
        try:
            nc = await target.create_category(name=cat.name, position=cat.position, overwrites=overwrites)
            catmap[cat.id] = nc
        except discord.Forbidden:
            log(f"No permission to create category: {cat.name}", "debug")
        except Exception:
            pass
        tick()

    log("Cloning channels..", "info")
    async def clonechannel(ch):
        overwrites = {}
        if not rolesfailed:
            for r, perms in ch.overwrites.items():
                if isinstance(r, discord.Role):
                    mapped = rolemap.get(r.id)
                    if mapped:
                        overwrites[mapped] = perms
                    elif r.is_default():
                        overwrites[target.default_role] = perms
        cat = catmap.get(ch.category_id) if ch.category_id else None
        try:
            if isinstance(ch, discord.TextChannel):
                await target.create_text_channel(
                    name=ch.name,
                    topic=ch.topic,
                    slowmode_delay=ch.slowmode_delay,
                    nsfw=ch.nsfw,
                    position=ch.position,
                    category=cat,
                    overwrites=overwrites
                )
            elif isinstance(ch, discord.VoiceChannel):
                await target.create_voice_channel(
                    name=ch.name,
                    bitrate=min(ch.bitrate, target.bitrate_limit),
                    user_limit=ch.user_limit,
                    position=ch.position,
                    category=cat,
                    overwrites=overwrites
                )
        except discord.Forbidden:
            log(f"No permission to create channel: {ch.name}", "debug")
        except Exception:
            pass
        tick()
    await asyncio.gather(*[clonechannel(ch) for ch in srcchannels])

    log("Removing existing emojis..", "info")
    async def deleteemoji(e):
        try:
            await e.delete()
        except discord.Forbidden:
            log(f"No permission to delete emoji: {e.name}", "debug")
        except Exception:
            pass
        tick()
    await asyncio.gather(*[deleteemoji(e) for e in existingemojis])

    log("Removing existing stickers..", "info")
    async def deletesticker(s):
        try:
            await s.delete()
        except discord.Forbidden:
            log(f"No permission to delete sticker: {s.name}", "debug")
        except Exception:
            pass
        tick()
    await asyncio.gather(*[deletesticker(s) for s in existingstickers])

    log("Cloning emojis..", "info")
    if not srcemojis:
        log("No emojis found, skipping", "warn")
    else:
        slotsfull = False
        for emoji in srcemojis:
            if slotsfull:
                tick()
                continue
            try:
                img = await fetchbytes(str(emoji.url))
                if img:
                    await target.create_custom_emoji(name=emoji.name, image=img)
            except discord.Forbidden:
                log("No permission to create emojis", "debug")
            except discord.HTTPException as e:
                if e.code == 30008 or "maximum" in str(e).lower():
                    log("Emoji slots full, skipping remaining emojis", "warn")
                    slotsfull = True
                else:
                    log(f"Failed to clone emoji {emoji.name}: {e}", "debug")
            except Exception:
                pass
            tick()

    log("Cloning stickers..", "info")
    if not srcstickers:
        log("No stickers found, skipping", "warn")
    else:
        import io
        stickersfull = False
        for sticker in srcstickers:
            if stickersfull:
                tick()
                continue
            try:
                img = await fetchbytes(sticker.url)
                if img:
                    ext = sticker.url.split(".")[-1].split("?")[0] or "png"
                    tag = sticker.emoji if hasattr(sticker, "emoji") and sticker.emoji else "ðŸ”¥"
                    await target.create_sticker(
                        name=sticker.name,
                        description=sticker.description or sticker.name,
                        emoji=tag,
                        file=discord.File(fp=io.BytesIO(img), filename=f"{sticker.name}.{ext}")
                    )
            except discord.Forbidden:
                log("No permission to create stickers", "debug")
            except discord.HTTPException as e:
                if e.code == 30073 or "maximum" in str(e).lower():
                    log("Sticker slots full, skipping remaining stickers", "warn")
                    stickersfull = True
                else:
                    log(f"Failed to clone sticker {sticker.name}: {e}", "debug")
            except Exception:
                pass
            tick()

    endbar()
    log(f"Successfully cloned '{source.name}' into '{targetname}'!", "success")


async def run():
    token = loadtoken()
    client = discord.Client()
    log("Logging into user..", "info")

    @client.event
    async def on_ready():
        log(f"Successfully logged into {client.user}", "success")
        await asyncio.sleep(0.4)
        guilds = list(client.guilds)
        if not guilds:
            log("No servers found.", "warn")
            await client.close()
            return
        source = pickserver(guilds, "Select the server to clone")
        eligible = [g for g in guilds if g.id != source.id and hascloningperms(g)]
        if not eligible:
            os.system("clear")
            header()
            log("No servers found where you have enough permissions to clone into.", "fail")
            log("You need Administrator or Manage Channels + Manage Roles on the target server.", "warn")
            await client.close()
            return
        target = pickserver(eligible, "Select the server to clone into\n  (if you do not see a server it means you don't have access to manage it)")
        os.system("clear")
        header()
        try:
            await cloneserver(source, target)
        except discord.Forbidden:
            endbar()
            log("Clone failed: missing permissions on the target server.", "fail")
            log("Fix: make sure the account has Administrator or Manage Channels + Manage Roles.", "warn")
        except discord.HTTPException as e:
            endbar()
            log(f"Clone failed: Discord returned HTTP {e.status} â€” {e.text}", "fail")
            log("Fix: check rate limits or if the server has too many channels/roles.", "warn")
        except Exception as e:
            endbar()
            log(f"Unexpected error: {type(e).__name__}: {e}", "fail")
        print()
        await client.close()

    try:
        await client.start(token)
    except discord.LoginFailure:
        log("Invalid token.", "fail")
    except Exception as e:
        log(f"Failed to connect: {type(e).__name__}: {e}", "fail")


os.system("clear")
header()
asyncio.run(run())

