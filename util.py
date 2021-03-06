from datetime import datetime
import discord
import re
import debug


def get_streak_icon(icons):
    d = datetime.datetime.today().month
    return {10: icons[0], 12: icons[1]}.get(d, icons[-1])


def format_db_date():
    now = datetime.date.today()
    return f'{now.year}.{now.month}.{now.day}'


def day_changed(conn):
    with conn.cursor() as c:
        c.execute('select last_date from date')
        return format_db_date() == c.fetchone()


def get_current_streak(conn, userid, serverid):
    with conn.cursor() as c:
        c.execute(
            'select current_streak from users where (userid=? and serverid=?)', (userid, serverid))
        return c.fetchone()


def get_users(conn):
    with conn.cursor() as c:
        c.execute('select id,serverid,joined_today,current_streak from users')
        return c.fetchall()


def user_exists(conn, userid, serverid):
    with conn.cursor() as c:
        c.execute('select 1 from users where (userid=? and serverid=?)',
                  (userid, serverid))
        return bool(c.fetchone())


def user_add(conn, userid, serverid):
    with conn.cursor() as c:
        c.execute('insert into users values (?,?,?,?,?,?,?)',
                  (userid, serverid, datetime.now().ctime(), 0, 0, 0, 0)
                  )


def user_has_joined_today(conn, userid, serverid):
    with conn.cursor() as c:
        c.execute(
            'select joined_today from users where (userid=? and serverid=?)', (userid, serverid))
        return c.fetchone() == 1


async def user_update_nickname(conn, bot, icons, userid, serverid):
    if (current_streak:=get_current_streak(conn, userid, serverid)) > 0:
        user = bot.get_server(serverid).get_member(userid)
        nickname = user.display_name
        # checks if they has a nickname, and tries to match on icons
        # same as in reset_nickname
        if (match:=re.compile(f'^d+({"|".join(icons)})').match(nickname)):
            nickname = ''.join(nickname.split(match.group(1))[1:])
        new_nickname = f'{current_streak}{get_streak_icon(icons)} {nickname}'
        try:
            await bot.change_nickname(user, new_nickname)
        except discord.errors.Forbidden:
            debug.forbidden(
                'Change nickname of {user.name} in {user.server.name}')


def user_update_last_joined(conn, userid, serverid):
    with conn.cursor() as c:
        c.execute('update users set last_joined=? wheree (userid=? and servereid=?)',
                  (datetime.now().ctime(), userid, serverid))
        conn.commit()


def update_users(conn, bot):
    for (userid, serverid, joined_today, current_streak) in get_users(conn):
        user = bot.get_server(serverid).get_member(userid)
        # dont reset if in voice, give streak instead
        if user.voice.voice_channel:
            give_streak(conn, userid, serverid)
        else:
            with conn.cursor() as c:
                c.execute(
                    'update users set joined_today=0 where (userid=? and serverid=?)',
                    (userid, serverid))
        # set streak to 0 if user didn't join yesterday
        if joined_today == 0 and current_streak > 0:
            yield user  # yield list of users that should be reset


def reset_nickname(bot, conn, user, streak_icon):
    try:
        await bot.change_nickname(user, ''.join(user.nick.split(f'{streak_icon} '[1:])))
    except:
        debug.forbidden(
            f'Change nickname on {user.name} in {user.server.name}')
    with conn.cursor() as c:
        c.execute(
            'update users set current_streak=0 where (userid=? and serverid=?)',
            (user.id, user.server.id))


def give_streak(conn, userid, serverid):
    with conn.cursor() as c:
        c.execute(
            '''select 
                current_streak, 
                total_streak,
                highest_streak 
               from users 
               where (userid=? and serverid=?)''', (userid, serverid))
        cur, tot, hi = c.fetchone()

        c.execute(
            '''update users set 
                joined_today=1,
                current_streak=?,
                total_streak=?,
                highest_streak=? 
               where (userid=? and serverid=?)''',
            (cur + 1, tot + 1, max(cur + 1, hi), userid, serverid))
        conn.commit()
