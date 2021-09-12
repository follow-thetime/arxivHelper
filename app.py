import os
import re
import time
from slack_bolt import App
from slack_bolt.oauth.oauth_settings import OAuthSettings
from slack_sdk.oauth.installation_store import FileInstallationStore
from slack_sdk.oauth.state_store import FileOAuthStateStore
import urllib.request
import feedparser
import pymysql

oauth_settings = OAuthSettings(
    client_id=os.environ["SLACK_CLIENT_ID"],
    client_secret=os.environ["SLACK_CLIENT_SECRET"],
    scopes=["app_mentions:read", "channels:history", "groups:history", "chat:write", "commands", "im:history", "im:read",
            "im:write", "incoming-webhook", "mpim:history", "mpim:read", "mpim:write"],
    installation_store=FileInstallationStore(base_dir="./data"),
    state_store=FileOAuthStateStore(expiration_seconds=600, base_dir="./data")
)

app = App(
    # token=os.environ['SLACK_BOT_TOKEN'],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
    oauth_settings=oauth_settings
)

url_Reg = r"https://arxiv.org/abs/([\w.]+)"
last_Message = ''


def get_feed(query):
    base_url = 'http://export.arxiv.org/api/query?'
    feedparser._FeedParserMixin.namespaces['http://a9.com/-/spec/opensearch/1.1/'] = 'opensearch'
    feedparser._FeedParserMixin.namespaces['http://arxiv.org/schemas/atom'] = 'arxiv'
    response = urllib.request.urlopen(base_url + query).read()
    feed = feedparser.parse(response)
    return feed


def get_links_from_feed(feed, max_link_num):
    papers = []
    for entry in feed.entries:
        paper_title = entry.title.replace('\n', '').replace('\r', '')
        paper_title = '['+paper_title+']'
        for link in entry.links:
            if link.rel == 'alternate':
                link = '('+link.href+')'
                papers.append(paper_title+link)
    papers = papers[0:max_link_num]
    return papers


def new_for_user(arxiv_id, user):
    connect = pymysql.connect(host='localhost', port=3306, user='root', passwd='mysql1999',
                              database='arxivurls', charset='utf8')
    cursor = connect.cursor()
    count = cursor.execute(f"select users from post where arxivid='{arxiv_id}'")
    if count == 0:
        cursor.close()
        connect.close()
        return 1
    else:
        users = cursor.fetchone()[0]
        if user not in users:
            cursor.close()
            connect.close()
            return 2
    cursor.close()
    connect.close()
    return 0


def no_past_tag(arxiv_id, user, username, tags):
    if tags:
        connect = pymysql.connect(host='localhost', port=3306, user='root', passwd='mysql1999', database='arxivurls',
                                  charset='utf8')
        cursor = connect.cursor()
        cursor.execute(f"select postname from post where arxivid='{arxiv_id}'")
        post_name = cursor.fetchone()[0]
        post_path = "./arxivPaperPage/_posts/" + post_name
        tag_input = tags + f'&emsp;&emsp;-assigned by {username}\n'
        with open(post_path, 'r', encoding='utf-8') as fp:
            content = fp.read()
            tag_tab = re.search('Comments:', content)
            tag_position = tag_tab.span()[0]
            with open(post_path, 'w') as f:
                content = content[:tag_position] + tag_input + content[tag_position:]
                f.write(content)
        cursor.execute(f"update userinput set tags='{tags}' where arxivid='{arxiv_id}' and user='{user}'")
        connect.commit()
        cursor.close()
        connect.close()


def no_past_comment(arxiv_id, user, username, comment):
    if comment:
        connect = pymysql.connect(host='localhost', port=3306, user='root', passwd='mysql1999', database='arxivurls',
                                  charset='utf8')
        cursor = connect.cursor()
        cursor.execute(f"select postname from post where arxivid='{arxiv_id}'")
        post_name = cursor.fetchone()[0]
        post_path = "./arxivPaperPage/_posts/" + post_name
        comment_input = f'comment from {username}:\n&emsp;&emsp;' + comment + '\n'
        with open(post_path, 'r', encoding='utf-8') as fp:
            content = fp.read()
            comment_tab = re.search('Title:', content)
            comment_pos = comment_tab.span()[0]
            with open(post_path, 'w', encoding='utf-8') as f:
                content = content[:comment_pos] + comment_input + content[comment_pos:]
                f.write(content)
        cursor.execute(f"update userinput set comment='{comment}' where arxivid='{arxiv_id}' and user='{user}'")
        connect.commit()
        cursor.close()
        connect.close()


def add_new_input(arxiv_id, user, username, tags, comment):
    connect = pymysql.connect(host='localhost', port=3306, user='root', passwd='mysql1999', database='arxivurls',
                              charset='utf8')
    cursor = connect.cursor()
    cursor.execute(f"select postname from post where arxivid='{arxiv_id}'")
    post_name = cursor.fetchone()[0]
    post_path = "./arxivPaperPage/_posts/" + post_name
    post_time = time.strftime("%Y-%m-%d", time.localtime())
    tag_input = tags + f'&emsp;&emsp;-assigned by {username}\n'
    comment_input = f'comment from {username}:\n&emsp;&emsp;' + comment + '\n'
    with open(post_path, 'r', encoding='utf-8') as fp:
        content = fp.read()
        tag_tab = re.search('Comments:', content)
        tag_position = tag_tab.span()[0]
        comment_tab = re.search('Title:', content)
        comment_pos = comment_tab.span()[0]
        if tags and comment:
            with open(post_path, 'w', encoding='utf-8') as f:
                content = content[:tag_position] + tag_input + content[tag_position:comment_pos] + \
                          comment_input + content[comment_pos:]
                f.write(content)
        elif tags and not comment:
            with open(post_path, 'w', encoding='utf-8') as f:
                content = content[:tag_position] + tag_input + content[tag_position:]
                f.write(content)
        elif not tags and comment:
            with open(post_path, 'w', encoding='utf-8') as f:
                content = content[:comment_pos] + comment_input + content[comment_pos:]
                f.write(content)
    cursor.execute(f"select users from post where arxivid='{arxiv_id}'")
    users = cursor.fetchone()[0]
    cursor.execute(f"update post set users='{users}, {user}' where arxivid='{arxiv_id}'")
    cursor.execute(f"insert into userinput values('{arxiv_id}','{user}','{post_time}','{tags}','{comment}')")
    connect.commit()
    cursor.close()
    connect.close()


def rewrite_past_input(arxiv_id, user, username, tags, comment):
    connect = pymysql.connect(host='localhost', port=3306, user='root', passwd='mysql1999', database='arxivurls',
                              charset='utf8')
    cursor = connect.cursor()
    cursor.execute(f"select postname from post where arxivid='{arxiv_id}'")
    post_name = cursor.fetchone()[0]
    post_path = "./arxivPaperPage/_posts/" + post_name
    cursor.execute(f"select tags from userinput where arxivid='{arxiv_id}' and user='{user}'")
    past_tag = cursor.fetchone()[0]
    cursor.execute(f"select comment from userinput where arxivid='{arxiv_id}' and user='{user}'")
    past_comment = cursor.fetchone()[0]
    post_time = time.strftime("%Y-%m-%d", time.localtime())
    if not past_tag and not past_comment:
        no_past_tag(arxiv_id, user, username, tags)
        no_past_comment(arxiv_id, user, username, comment)
    elif not past_tag and past_comment:
        no_past_tag(arxiv_id, user, username, tags)
        with open(post_path, 'r', encoding='utf-8') as fp:
            content = fp.read()
            if comment:
                with open(post_path, 'w', encoding='utf-8') as f:
                    temp = re.sub(past_comment, comment, content)
                    f.write(temp)
                cursor.execute(f"update userinput set comment='{comment}' where arxivid='{arxiv_id}' and user='{user}'")
    elif past_tag and not past_comment:
        no_past_comment(arxiv_id, user, username, comment)
        with open(post_path, 'r', encoding='utf-8') as fp:
            content = fp.read()
            if tags:
                with open(post_path, 'w', encoding='utf-8') as f:
                    temp = re.sub(past_tag, tags, content)
                    f.write(temp)
                cursor.execute(f"update userinput set tags='{tags}' where arxivid='{arxiv_id}' and user='{user}'")
    elif past_tag and past_comment:
        with open(post_path, 'r', encoding='utf-8') as fp:
            content = fp.read()
            if tags and comment:
                with open(post_path, 'w', encoding='utf-8') as f:
                    temp1 = re.sub(past_tag, tags, content)
                    temp2 = re.sub(past_comment, comment, temp1)
                    f.write(temp2)
            elif tags and not comment:
                with open(post_path, 'w', encoding='utf-8') as f:
                    temp = re.sub(past_tag, tags, content)
                    f.write(temp)
            elif not tags and comment:
                with open(post_path, 'w', encoding='utf-8') as f:
                    temp = re.sub(past_comment, comment, content)
                    f.write(temp)
        if tags:
            cursor.execute(f"update userinput set tags='{tags}' where arxivid='{arxiv_id}' and user='{user}'")
        if comment:
            cursor.execute(f"update userinput set comment='{comment}' where arxivid='{arxiv_id}' and user='{user}'")
    cursor.execute(f"update userinput set posttime='{post_time}' where arxivid='{arxiv_id}' and user='{user}'")
    connect.commit()
    cursor.close()
    connect.close()


def append_past_input(arxiv_id, user, username, tags, comment):
    connect = pymysql.connect(host='localhost', port=3306, user='root', passwd='mysql1999', database='arxivurls',
                              charset='utf8')
    cursor = connect.cursor()
    cursor.execute(f"select postname from post where arxivid='{arxiv_id}'")
    post_name = cursor.fetchone()[0]
    post_path = "./arxivPaperPage/_posts/" + post_name
    cursor.execute(f"select tags from userinput where arxivid='{arxiv_id}' and user='{user}'")
    past_tag = cursor.fetchone()[0]
    new_tag = past_tag + ', ' + tags
    cursor.execute(f"select comment from userinput where arxivid='{arxiv_id}' and user='{user}'")
    past_comment = cursor.fetchone()[0]
    post_time = time.strftime("%Y-%m-%d", time.localtime())
    comment_input = f'added on {post_time}:\n&emsp;&emsp;' + comment
    new_comment = past_comment + '\n' + comment_input
    if not past_tag and not past_comment:
        no_past_tag(arxiv_id, user, username, tags)
        no_past_comment(arxiv_id, user, username, comment)
    elif not past_tag and past_comment:
        no_past_tag(arxiv_id, user, username, tags)
        with open(post_path, 'r', encoding='utf-8') as fp:
            content = fp.read()
            comment_tab = re.search(past_comment + '\n', content)
            comment_pos = comment_tab.span()[1]
            if comment:
                with open(post_path, 'w', encoding='utf-8') as f:
                    content = content[:comment_pos] + comment_input + '\n' + content[comment_pos:]
                    f.write(content)
                cursor.execute(f"update userinput set comment='{new_comment}' where arxivid='{arxiv_id}' and user='{user}'")
    elif past_tag and not past_comment:
        no_past_comment(arxiv_id, user, username, comment)
        with open(post_path, 'r', encoding='utf-8') as fp:
            content = fp.read()
            tag_tab = re.search(past_tag, content)
            tag_position = tag_tab.span()[1]
            if tags:
                with open(post_path, 'w', encoding='utf-8') as f:
                    content = content[:tag_position] + ', ' + tags + content[tag_position:]
                    f.write(content)
                cursor.execute(f"update userinput set tags='{new_tag}' where arxivid='{arxiv_id}' and user='{user}'")
    elif past_tag and past_comment:
        with open(post_path, 'r', encoding='utf-8') as fp:
            content = fp.read()
            tag_tab = re.search(past_tag, content)
            tag_position = tag_tab.span()[1]
            comment_tab = re.search(past_comment+'\n', content)
            comment_pos = comment_tab.span()[1]
            if tags and comment:
                with open(post_path, 'w', encoding='utf-8') as f:
                    content = content[:tag_position] + ', ' + tags + content[tag_position:comment_pos] + \
                              comment_input + '\n' + content[comment_pos:]
                    f.write(content)
            elif tags and not comment:
                with open(post_path, 'w', encoding='utf-8') as f:
                    content = content[:tag_position] + ', ' + tags + content[tag_position:]
                    f.write(content)
            elif not tags and comment:
                with open(post_path, 'w', encoding='utf-8') as f:
                    content = content[:comment_pos] + comment_input + '\n' + content[comment_pos:]
                    f.write(content)
        if tags:
            cursor.execute(f"update userinput set tags='{new_tag}' where arxivid='{arxiv_id}' and user='{user}'")
        if comment:
            cursor.execute(f"update userinput set comment='{new_comment}' where arxivid='{arxiv_id}' and user='{user}'")
    cursor.execute(f"update userinput set posttime='{post_time}' where arxivid='{arxiv_id}' and user='{user}'")
    connect.commit()
    cursor.close()
    connect.close()


def window_filename(name):
    name = name.strip().replace('\n', '').replace('\r', '')
    name = name.replace('\\', '')
    name = name.replace('/', '')
    name = name.replace('<', '')
    name = name.replace('>', '')
    name = name.replace('?', '')
    name = name.replace('*', '')
    name = name.replace('"', '')
    name = name.replace(':', '')
    name = name.replace('|', '')
    return name


def create_post(arxiv_id, user, username, tags, comment):
    connect = pymysql.connect(host='localhost', port=3306, user='root', passwd='mysql1999', database='arxivurls', charset='utf8')
    cursor = connect.cursor()
    post_time = time.strftime("%Y-%m-%d", time.localtime())
    post_url = 'https://arxiv.org/abs/' + arxiv_id
    query = 'id_list=%s' % arxiv_id
    feed = get_feed(query)
    entry = feed.entries[0]
    title = entry.title
    authors = ''
    try:
        authors = ', '.join(author.name for author in entry.authors)
    except AttributeError:
        pass
    tag_list = [t['term'] for t in entry.tags]
    suggested_tag = ', '.join(tag_list)
    summary = entry.summary
    summary = summary.replace('\r', '').replace('\n', '')
    title_name = window_filename(title)
    post_name = post_time + "-" + f'{title_name}.md'
    post_path = "./arxivPaperPage/_posts/" + post_name
    last_author = authors.split(',')[-1].strip().replace(' ', '+')
    query1 = f'search_query=au:{last_author}&start=0&max_result=5'
    feed = get_feed(query1)
    relevant1 = get_links_from_feed(feed, 5)
    r1 = '\n&emsp;'.join(link for link in relevant1)
    r1 = '&emsp;' + r1
    r2 = ''
    if tags:
        relevant2 = []
        tag_list = [tag.strip() for tag in tags.split(',')]
        each_max = 1 if len(tag_list) > 5 else int(6 / len(tag_list))
        try:
            for tag in tag_list:
                query = f'search_query=cat:{tag}&start=0&max_result={each_max}'
                feed = get_feed(query)
                relevant2.extend(get_links_from_feed(feed, each_max))
            r2 = '\n&emsp;'.join(link for link in relevant2)
        except:
            pass
    else:
        relevant2 = []
        tag_list = [tag.strip() for tag in suggested_tag.split(',')]
        each_max = 1 if len(tag_list) > 5 else int(6 / len(tag_list))
        for tag in tag_list:
            query = f'search_query=cat:{tag}&start=0&max_result={each_max}'
            feed = get_feed(query)
            relevant2.extend(get_links_from_feed(feed, each_max))
        r2 = '\n&emsp;'.join(link for link in relevant2)
    r2 = '&emsp;' + r2
    tag_in_post = ''
    comment_in_post = ''
    if tags:
        tag_in_post = f'{tags}&emsp;&emsp;-assigned by {username}'
    if comment:
        comment_in_post = f'comment from {username}:\n&emsp;&emsp;{comment} '
    post_data = \
f'''
---
layout: post
---
Url of paper: {post_url}
posted by: {username}
Tags:\n{tag_in_post}
Comments:\n{comment_in_post}
Title:{title}
Abstract:{summary}
Relevant papers:
papers from the same last author:
{r1}
papers of similar category(tag):
{r2}'''
    with open(post_path, 'w', encoding='utf-8') as fp:
        fp.write(post_data)
    cursor.execute(f"insert into post values(default,'{arxiv_id}','{post_time}','{user}','{post_name}')")
    cursor.execute(f"insert into userinput values('{arxiv_id}','{user}','{post_time}','{tags}','{comment}')")
    connect.commit()
    cursor.close()
    connect.close()


@app.event("app_home_opened")
def home_opened(client, event, logger):
    try:
        client.views_publish(
            user_id=event['user'],
            view={
                "type": "home",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "plain_text",
                            "text": "welcome home!",
                            "emoji": True
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Thanks for using arxivHelper, this is a slack bot to help you deal with arXiv urls, and there is a static web site(https://follow-thetime.github.io/arxivPaperPage/) to store interesting urls posted by users during the usage of this bot."
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "plain_text",
                            "text": "You can use this bot by easily typing the url of the arxiv paper that interests you to any channel this bot was added to, then follow the guidance and do what you want. Or you can use slash commands. For more instructions, you can type '@arxivHelper' in the channel.",
                            "emoji": True
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "plain_text",
                                "text": "Version: 1.0",
                                "emoji": True
                            }
                        ]
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "plain_text",
                                "text": "Author: Sheng Guo",
                                "emoji": True
                            }
                        ]
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "plain_text",
                                "text": "Email: ka20939@bristol.ac.uk",
                                "emoji": True
                            }
                        ]
                    }
                ]
            }
        )
    except Exception as e:
        logger.error(f"Error publishing home tab: {e}")


@app.event("app_mention")
def app_mention(ack, body, say):
    ack()
    say({"blocks": [
            {
                "type": "section",
                "text": {
                    "type": "plain_text",
                    "text": f"Hello <@{body['event']['user']}>!",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "This is a slcak bot to help you deal with arXiv urls, and there is a static web site(https://follow-thetime.github.io/arxivPaperPage/) to store interesting urls posted by you during the usage of this bot."
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "plain_text",
                    "text": "You can use this bot by typing an url of arxiv paper, or you can use slash commands:",
                    "emoji": True
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "By using */post (url you want to post)</font>* you can simply post an url to the web site;"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "By using */tag (tags you assign to the paper) (url you want to post)* you can post an url with tags to the web site; if you had assigned tags to it before, it will cover the past tags;"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "By using */comment (comments you write for the paper) (url you want to post)*  you can post an url with comments to the web site; also you may cover your past comment;"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "By using */comtag (tags) (url) (comments)* you can post an url with tags and comments to the web site; also you may cover the past content;"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": "If you want to add something to your past input, please type the url in the channel.",
                        "emoji": True
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "plain_text",
                    "text": "For more information, please go to app home page.",
                    "emoji": True
                }
            }
        ]})


@app.message(url_Reg)
def message_url(message, say):
    global last_Message
    last_Message = message['text']
    arxiv_id = re.search(url_Reg, last_Message).group(1)
    user = message['user']
    if new_for_user(arxiv_id, user) == 1:
        say({
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "plain_text",
                        "text": "It looks like there is a new url that never appears before!"
                                "Click the button to deal with it: "
                    },
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "click me",
                            "emoji": True
                        },
                        "value": "click_me_123",
                        "action_id": "new_url_dealing"
                    }
                }
            ]
        })
    elif new_for_user(arxiv_id, user) == 0:
        say({
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "plain_text",
                        "text": "It seems that you had dealt with this paper before!"
                                "Click the button to make some changes: "
                    },
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "click me",
                            "emoji": True
                        },
                        "value": "click_me_123",
                        "action_id": "old_url_dealing"
                    }
                }
            ]
        })
    else:
        say({
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "plain_text",
                        "text": "It looks like someone had dealt with this paper before!"
                                "Click the button to join him(her): "
                    },
                    "accessory": {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "click me",
                            "emoji": True
                        },
                        "value": "click_me_123",
                        "action_id": "new_url_dealing"
                    }
                }
            ]
        })


@app.action('new_url_dealing')
def deal_item(ack, body, client, say):
    ack()
    if re.search(url_Reg, last_Message):
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "new_checkbox_view",
                "title": {
                    "type": "plain_text",
                    "text": "deal with arxiv url",
                    "emoji": True
                },
                "submit": {
                    "type": "plain_text",
                    "text": "Submit",
                    "emoji": True
                },
                "close": {
                    "type": "plain_text",
                    "text": "Cancel",
                    "emoji": True
                },
                "blocks": [
                    {
                        "type": "section",
                        "block_id": "checkbox_block",
                        "text": {
                            "type": "plain_text",
                            "text": "Choose what you'd like to do with the url :"
                        },
                        "accessory": {
                            "type": "checkboxes",
                            "action_id": "checkBox",
                            "initial_options": [
                                {
                                    "value": "value-0",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "post it"
                                    },
                                    "description": {
                                        "type": "plain_text",
                                        "text": "if you do not post it, other behaviors might be meaningless!",
                                        "emoji": True
                                    }
                                }
                            ],
                            "options": [
                                {
                                    "value": "value-0",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "post it"
                                    },
                                    "description": {
                                        "type": "plain_text",
                                        "text": "if you do not post it, other behaviors might be meaningless!",
                                        "emoji": True
                                    }
                                },
                                {
                                    "value": "value-1",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "add tags"
                                    }
                                },
                                {
                                    "value": "value-2",
                                    "text": {
                                        "type": "plain_text",
                                        "text": "add comments"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        )
    else:
        say('please type an arxiv url you want to deal with to start!')


@app.action('old_url_dealing')
def old_url_dealing(ack, body, client):
    ack()
    if re.search(url_Reg, last_Message):
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "old_checkbox_view",
                "title": {
                    "type": "plain_text",
                    "text": "Make some changes",
                    "emoji": True
                },
                "submit": {
                    "type": "plain_text",
                    "text": "Submit",
                    "emoji": True
                },
                "close": {
                    "type": "plain_text",
                    "text": "Cancel",
                    "emoji": True
                },
                "blocks": [
                    {
                        "type": "section",
                        "block_id": "tag_radio_block",
                        "text": {
                            "type": "plain_text",
                            "text": "About tags:"
                        },
                        "accessory": {
                            "type": "radio_buttons",
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "reassign tags",
                                        "emoji": True
                                    },
                                    "value": "value-0"
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "add another tag or several new tags",
                                        "emoji": True
                                    },
                                    "value": "value-1"
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "keep the same and don't make changes",
                                        "emoji": True
                                    },
                                    "value": "value-2"
                                }
                            ],
                            "action_id": "tag_choice"
                        }
                    },
                    {
                        "type": "section",
                        "block_id": "comment_radio_block",
                        "text": {
                            "type": "plain_text",
                            "text": "About comments:"
                        },
                        "accessory": {
                            "type": "radio_buttons",
                            "options": [
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "rewrite your comments",
                                        "emoji": True
                                    },
                                    "value": "value-0"
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "add a new comment",
                                        "emoji": True
                                    },
                                    "value": "value-1"
                                },
                                {
                                    "text": {
                                        "type": "plain_text",
                                        "text": "keep the same and don't make changes",
                                        "emoji": True
                                    },
                                    "value": "value-2"
                                }
                            ],
                            "action_id": "comment_choice"
                        }
                    }
                ]
            }
        )


@app.view('new_checkbox_view')
def get_user_input(ack, view, body, client):
    ack()
    print(body)
    selected = view["state"]["values"]["checkbox_block"]["checkBox"]["selected_options"]
    selected_options = [x["value"] for x in selected]
    arxiv_id = re.search(url_Reg, last_Message).group(1)
    query = 'id_list=%s' % arxiv_id
    feed = get_feed(query)
    entry = feed.entries[0]
    title = entry.title.replace('\r', '').replace('\n', '')
    authors = ''
    try:
        authors = ', '.join(author.name for author in entry.authors)
    except AttributeError:
        pass
    try:
        arxiv_comment = entry.arxiv_comment.replace('\r', '').replace('\n', '')
    except AttributeError:
        arxiv_comment = 'No comment found'
    tag_list = [t['term'] for t in entry.tags]
    suggested_tag = ', '.join(tag_list)
    summary = entry.summary
    summary = summary.replace('\r', '').replace('\n', '')
    if "value-0" in selected_options:
        if "value-1" in selected_options and "value-2" in selected_options:
            client.views_open(
                trigger_id=body["trigger_id"],
                view={
                    "type": "modal",
                    "callback_id": "both_input_view",
                    "title": {
                        "type": "plain_text",
                        "text": "deal with arxiv url",
                        "emoji": True
                    },
                    "submit": {
                        "type": "plain_text",
                        "text": "Submit",
                        "emoji": True
                    },
                    "close": {
                        "type": "plain_text",
                        "text": "Cancel",
                        "emoji": True
                    },
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "plain_text",
                                "text": f"Title of the paper:\n {title}"
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "plain_text",
                                "text": f"Authors:\n {authors}"
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "plain_text",
                                "text": f"Arxiv's comment:\n{arxiv_comment}"
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "plain_text",
                                "text": f"Abstract:\n{summary}"
                            }
                        },
                        {
                            "type": "divider"
                        },
                        {
                            "type": "input",
                            "block_id": "input_block_1",
                            "element": {
                                "type": "plain_text_input",
                                "action_id": "tag_input"
                            },
                            "label": {
                                "type": "plain_text",
                                "text": f"assign a tag or several tags for it(suggested ones:{suggested_tag}):",
                                "emoji": True
                            },
                        },
                        {
                            "type": "input",
                            "block_id": "input_block_2",
                            "element": {
                                "type": "plain_text_input",
                                "multiline": True,
                                "action_id": "comment_input"
                            },
                            "label": {
                                "type": "plain_text",
                                "text": "write down your comment about it:",
                                "emoji": True
                            }
                        }
                    ]
                })
        elif "value-1" in selected_options and "value-2" not in selected_options:
            client.views_open(
                trigger_id=body["trigger_id"],
                view={
                    "type": "modal",
                    "callback_id": "tag_input_view",
                    "title": {
                        "type": "plain_text",
                        "text": "deal with arxiv url",
                        "emoji": True
                    },
                    "submit": {
                        "type": "plain_text",
                        "text": "Submit",
                        "emoji": True
                    },
                    "close": {
                        "type": "plain_text",
                        "text": "Cancel",
                        "emoji": True
                    },
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "plain_text",
                                "text": f"Title of the paper:\n {title}"
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "plain_text",
                                "text": f"Authors:\n {authors}"
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "plain_text",
                                "text": f"Arxiv's comment:\n{arxiv_comment}"
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "plain_text",
                                "text": f"Abstract:\n{summary}"
                            }
                        },
                        {
                            "type": "divider"
                        },
                        {
                            "type": "input",
                            "block_id": "input_block_1",
                            "element": {
                                "type": "plain_text_input",
                                "action_id": "tag_input"
                            },
                            "label": {
                                "type": "plain_text",
                                "text": f"assign a tag or several tags for it(suggested ones: {suggested_tag}):",
                                "emoji": True
                            },
                        }
                    ]
                })
        elif "value-1" not in selected_options and "value-2" in selected_options:
            client.views_open(
                trigger_id=body["trigger_id"],
                view={
                    "type": "modal",
                    "callback_id": "comment_input_view",
                    "title": {
                        "type": "plain_text",
                        "text": "deal with arxiv url",
                        "emoji": True
                    },
                    "submit": {
                        "type": "plain_text",
                        "text": "Submit",
                        "emoji": True
                    },
                    "close": {
                        "type": "plain_text",
                        "text": "Cancel",
                        "emoji": True
                    },
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "plain_text",
                                "text": f"Title of the paper:\n {title}"
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "plain_text",
                                "text": f"Authors:\n {authors}"
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "plain_text",
                                "text": f"Arxiv's comment:\n{arxiv_comment}"
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "plain_text",
                                "text": f"Abstract:\n{summary}"
                            }
                        },
                        {
                            "type": "divider"
                        },
                        {
                            "type": "input",
                            "block_id": "input_block_2",
                            "element": {
                                "type": "plain_text_input",
                                "multiline": True,
                                "action_id": "comment_input"
                            },
                            "label": {
                                "type": "plain_text",
                                "text": "write down your comment about it:",
                                "emoji": True
                            }
                        }
                    ]
                })
        else:
            user = body['user']['id']
            if new_for_user(arxiv_id,user) == 1:
                username = body['user']['username']
                create_post(arxiv_id, user, username, "", "")
                client.chat_postMessage(
                    channel=body['user']['id'],
                    text="You have posted this url to the web page!"
                )


@app.view("both_input_view")
def both_deal(ack, body, view, client):
    ack()
    print(body)
    tags = view['state']['values']['input_block_1']["tag_input"]['value']
    comments = view['state']['values']['input_block_2']['comment_input']['value']
    user = body['user']['id']
    username = body['user']['username']
    arxiv_id = re.search(url_Reg, last_Message).group(1)
    if new_for_user(arxiv_id, user) == 1:
        create_post(arxiv_id, user, tags, username, comments)
    elif new_for_user(arxiv_id, user) == 2:
        add_new_input(arxiv_id, user, tags, username, comments)
    client.chat_postMessage(
        channel=body['user']['id'],
        text="You have posted this url,tags and comments to the web page!"
    )


@app.view("tag_input_view")
def tag_deal(ack, body, view, client):
    ack()
    tags = view['state']['values']['input_block_1']["tag_input"]['value']
    user = body['user']['id']
    username = body['user']['username']
    arxiv_id = re.search(url_Reg, last_Message).group(1)
    if new_for_user(arxiv_id, user) == 1:
        create_post(arxiv_id, user, username, tags, '')
    elif new_for_user(arxiv_id, user) == 2:
        add_new_input(arxiv_id, user, username, tags, '')
    client.chat_postMessage(
        channel=body['user']['id'],
        text="You have posted this url and tags to the web page!"
    )


@app.view("comment_input_view")
def comment_deal(ack, body, view, client):
    ack()
    comments = view['state']['values']['input_block_2']['comment_input']['value']
    user = body['user']['id']
    username = body['user']['username']
    arxiv_id = re.search(url_Reg, last_Message).group(1)
    if new_for_user(arxiv_id, user) == 1:
        create_post(arxiv_id, user, username, '', comments)
    elif new_for_user(arxiv_id, user) == 2:
        add_new_input(arxiv_id, user, username, '', comments)
    client.chat_postMessage(
        channel=body['user']['id'],
        text="You have posted this url and your comment to the web page!"
    )


@app.view('old_checkbox_view')
def get_user_input(ack, view, body, client):
    ack()
    tag_value = view["state"]["values"]["tag_radio_block"]["tag_choice"]["selected_option"]["value"]
    comment_value = view["state"]["values"]["comment_radio_block"]["comment_choice"]["selected_option"]["value"]
    connect = pymysql.connect(host='localhost', port=3306, user='root', passwd='mysql1999', database='arxivurls',
                              charset='utf8')
    cursor = connect.cursor()
    arxiv_id = re.search(url_Reg, last_Message).group(1)
    user = body['user']['id']
    cursor.execute(f"select tags from userinput where arxivid='{arxiv_id}' and user='{user}'")
    past_tags = cursor.fetchone()[0]
    if not past_tags:
        past_tags = "you hadn't assigned any tags to this url."
    else:
        past_tags = f"last time you assigned:{past_tags} to this url."
    cursor.execute(f"select comment from userinput where arxivid='{arxiv_id}' and user='{user}'")
    past_comment = cursor.fetchone()[0]
    if not past_comment:
        past_comment = "you hadn't writen any comment for this url."
    else:
        past_comment = f"your comment last time is:{past_comment}"
    if tag_value == 'value-0' and comment_value == 'value-0':
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "view00",
                "title": {
                    "type": "plain_text",
                    "text": "make changes",
                    "emoji": True
                },
                "submit": {
                    "type": "plain_text",
                    "text": "Submit",
                    "emoji": True
                },
                "close": {
                    "type": "plain_text",
                    "text": "Cancel",
                    "emoji": True
                },
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "input_block_1",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "tag_input"
                        },
                        "label": {
                            "type": "plain_text",
                            "text": f"reassign a tag or several tags({past_tags}):",
                            "emoji": True
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "input_block_2",
                        "element": {
                            "type": "plain_text_input",
                            "multiline": True,
                            "action_id": "comment_input"
                        },
                        "label": {
                            "type": "plain_text",
                            "text": f"rewrite your comment({past_comment}):",
                            "emoji": True
                        }
                    }
                ]
            })
    elif tag_value == 'value-0' and comment_value == 'value-1':
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "view01",
                "title": {
                    "type": "plain_text",
                    "text": "make changes",
                    "emoji": True
                },
                "submit": {
                    "type": "plain_text",
                    "text": "Submit",
                    "emoji": True
                },
                "close": {
                    "type": "plain_text",
                    "text": "Cancel",
                    "emoji": True
                },
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "input_block_1",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "tag_input"
                        },
                        "label": {
                            "type": "plain_text",
                            "text": f"reassign a tag or several tags({past_tags}):",
                            "emoji": True
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "input_block_2",
                        "element": {
                            "type": "plain_text_input",
                            "multiline": True,
                            "action_id": "comment_input"
                        },
                        "label": {
                            "type": "plain_text",
                            "text": f"add another comment({past_comment}):",
                            "emoji": True
                        }
                    }
                ]
            })
    elif tag_value == 'value-0' and comment_value == 'value-2':
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "view02",
                "title": {
                    "type": "plain_text",
                    "text": "make changes",
                    "emoji": True
                },
                "submit": {
                    "type": "plain_text",
                    "text": "Submit",
                    "emoji": True
                },
                "close": {
                    "type": "plain_text",
                    "text": "Cancel",
                    "emoji": True
                },
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "input_block_1",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "tag_input"
                        },
                        "label": {
                            "type": "plain_text",
                            "text": f"reassign a tag or several tags({past_tags}):",
                            "emoji": True
                        },
                    }
                ]
            })
    elif tag_value == 'value-1' and comment_value == 'value-0':
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "view10",
                "title": {
                    "type": "plain_text",
                    "text": "make changes",
                    "emoji": True
                },
                "submit": {
                    "type": "plain_text",
                    "text": "Submit",
                    "emoji": True
                },
                "close": {
                    "type": "plain_text",
                    "text": "Cancel",
                    "emoji": True
                },
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "input_block_1",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "tag_input"
                        },
                        "label": {
                            "type": "plain_text",
                            "text": f"add another tag or several tags({past_tags}):",
                            "emoji": True
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "input_block_2",
                        "element": {
                            "type": "plain_text_input",
                            "multiline": True,
                            "action_id": "comment_input"
                        },
                        "label": {
                            "type": "plain_text",
                            "text": f"rewrite your comment({past_comment}):",
                            "emoji": True
                        }
                    }
                ]
            })
    elif tag_value == 'value-1' and comment_value == 'value-1':
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "both_add",
                "title": {
                    "type": "plain_text",
                    "text": "make changes",
                    "emoji": True
                },
                "submit": {
                    "type": "plain_text",
                    "text": "Submit",
                    "emoji": True
                },
                "close": {
                    "type": "plain_text",
                    "text": "Cancel",
                    "emoji": True
                },
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "input_block_1",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "tag_input"
                        },
                        "label": {
                            "type": "plain_text",
                            "text": f"add another tag or several tags({past_tags}):",
                            "emoji": True
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "input_block_2",
                        "element": {
                            "type": "plain_text_input",
                            "multiline": True,
                            "action_id": "comment_input"
                        },
                        "label": {
                            "type": "plain_text",
                            "text": f"add another comment({past_comment}):",
                            "emoji": True
                        }
                    }
                ]
            })
    elif tag_value == 'value-1' and comment_value == 'value-2':
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "view02",
                "title": {
                    "type": "plain_text",
                    "text": "make changes",
                    "emoji": True
                },
                "submit": {
                    "type": "plain_text",
                    "text": "Submit",
                    "emoji": True
                },
                "close": {
                    "type": "plain_text",
                    "text": "Cancel",
                    "emoji": True
                },
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "input_block_1",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "tag_input"
                        },
                        "label": {
                            "type": "plain_text",
                            "text": f"add another tag or several tags({past_tags}):",
                            "emoji": True
                        },
                    }
                ]
            })
    elif tag_value == 'value-2' and comment_value == 'value-0':
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "view20",
                "title": {
                    "type": "plain_text",
                    "text": "make changes",
                    "emoji": True
                },
                "submit": {
                    "type": "plain_text",
                    "text": "Submit",
                    "emoji": True
                },
                "close": {
                    "type": "plain_text",
                    "text": "Cancel",
                    "emoji": True
                },
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "input_block_2",
                        "element": {
                            "type": "plain_text_input",
                            "multiline": True,
                            "action_id": "comment_input"
                        },
                        "label": {
                            "type": "plain_text",
                            "text": f"rewrite your comment({past_comment}):",
                            "emoji": True
                        }
                    }
                ]
            })
    elif tag_value == 'value-2' and comment_value == 'value-1':
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "view21",
                "title": {
                    "type": "plain_text",
                    "text": "make changes",
                    "emoji": True
                },
                "submit": {
                    "type": "plain_text",
                    "text": "Submit",
                    "emoji": True
                },
                "close": {
                    "type": "plain_text",
                    "text": "Cancel",
                    "emoji": True
                },
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "input_block_2",
                        "element": {
                            "type": "plain_text_input",
                            "multiline": True,
                            "action_id": "comment_input"
                        },
                        "label": {
                            "type": "plain_text",
                            "text": f"add another comment({past_comment}):",
                            "emoji": True
                        }
                    }
                ]
            })
    else:
        pass
    cursor.close()
    connect.close()


@app.view("view00")
def view00(ack, body, view, client):
    ack()
    tags = view['state']['values']['input_block_1']["tag_input"]['value']
    comment = view['state']['values']['input_block_2']['comment_input']['value']
    user = body['user']['id']
    username = body['user']['username']
    arxiv_id = re.search(url_Reg, last_Message).group(1)
    rewrite_past_input(arxiv_id, user, username, tags, comment)
    client.chat_postMessage(
        channel=body['user']['id'],
        text="You have successfully reassigned tags and rewriten your comment!"
    )


@app.view("view01")
def view00(ack, body, view, client):
    ack()
    tags = view['state']['values']['input_block_1']["tag_input"]['value']
    comment = view['state']['values']['input_block_2']['comment_input']['value']
    user = body['user']['id']
    username = body['user']['username']
    arxiv_id = re.search(url_Reg, last_Message).group(1)
    rewrite_past_input(arxiv_id, user, username, tags, '')
    append_past_input(arxiv_id, user, username, '', comment)
    client.chat_postMessage(
        channel=body['user']['id'],
        text="You have successfully reassigned tags and added a new comment!"
    )


@app.view("view02")
def view00(ack, body, view, client):
    ack()
    tags = view['state']['values']['input_block_1']["tag_input"]['value']
    user = body['user']['id']
    username = body['user']['username']
    arxiv_id = re.search(url_Reg, last_Message).group(1)
    rewrite_past_input(arxiv_id, user, username, tags, '')
    client.chat_postMessage(
        channel=body['user']['id'],
        text="You have successfully reassigned tags to the url!"
    )


@app.view("view10")
def view00(ack, body, view, client):
    ack()
    tags = view['state']['values']['input_block_1']["tag_input"]['value']
    comment = view['state']['values']['input_block_2']['comment_input']['value']
    user = body['user']['id']
    username = body['user']['username']
    arxiv_id = re.search(url_Reg, last_Message).group(1)
    append_past_input(arxiv_id, user, username, tags, '')
    rewrite_past_input(arxiv_id, user, username, '', comment)
    client.chat_postMessage(
        channel=body['user']['id'],
        text="You have successfully added a new tag and rewriten your comment!"
    )


@app.view("view11")
def view00(ack, body, view, client):
    ack()
    tags = view['state']['values']['input_block_1']["tag_input"]['value']
    comment = view['state']['values']['input_block_2']['comment_input']['value']
    user = body['user']['id']
    username = body['user']['username']
    arxiv_id = re.search(url_Reg, last_Message).group(1)
    append_past_input(arxiv_id, user, username, tags, comment)
    client.chat_postMessage(
        channel=body['user']['id'],
        text="You have successfully added a new tag and a new comment!"
    )


@app.view("view12")
def view00(ack, body, view, client):
    ack()
    tags = view['state']['values']['input_block_1']["tag_input"]['value']
    user = body['user']['id']
    username = body['user']['username']
    arxiv_id = re.search(url_Reg, last_Message).group(1)
    append_past_input(arxiv_id, user, username, tags, '')
    client.chat_postMessage(
        channel=body['user']['id'],
        text="You have successfully added a new tag!"
    )


@app.view("view20")
def view00(ack, body, view, client):
    ack()
    comment = view['state']['values']['input_block_2']['comment_input']['value']
    user = body['user']['id']
    username = body['user']['username']
    arxiv_id = re.search(url_Reg, last_Message).group(1)
    rewrite_past_input(arxiv_id, user, username, '', comment)
    client.chat_postMessage(
        channel=body['user']['id'],
        text="You have successfully rewriten your comment!"
    )


@app.view("view21")
def view00(ack, body, view, client):
    ack()
    comment = view['state']['values']['input_block_2']['comment_input']['value']
    user = body['user']['id']
    username = body['user']['username']
    arxiv_id = re.search(url_Reg, last_Message).group(1)
    append_past_input(arxiv_id, user, username, '', comment)
    client.chat_postMessage(
        channel=body['user']['id'],
        text="You have successfully added a new comment!"
    )


@app.command("/post")
def post_command(ack, command, say):
    ack()
    url = command['text']
    user = command['user_id']
    username = command['user_name']
    arxiv_id = re.search(url_Reg, url).group(1)
    if new_for_user(arxiv_id, user) == 1:
        create_post(arxiv_id, user, username, "", "")
        say("You have posted this url to the web page!")
    else:
        say('This url had been posted by another user!')


@app.command("/tag")
def tag_command(ack, command, say):
    ack()
    match_obj = re.search(r"(.+)\s*(https://arxiv.org/abs/[\w.]+)\s*", command['text'])
    tags = match_obj.group(1)
    url = match_obj.group(2)
    user = command['user_id']
    username = command['user_name']
    arxiv_id = re.search(url_Reg, url).group(1)
    if new_for_user(arxiv_id, user) == 1:
        create_post(arxiv_id, user, username, tags, '')
    elif new_for_user(arxiv_id, user) == 2:
        add_new_input(arxiv_id, user, username, tags, '')
    else:
        rewrite_past_input(arxiv_id, user, username, tags, '')
    say("You have posted this url and tags to the web page!")


@app.command("/comment")
def comment_command(ack, command, say):
    ack()
    match_obj = re.search(r"(https://arxiv.org/abs/[\w.]+)\s*(.+)", command['text'])
    comment = match_obj.group(1)
    url = match_obj.group(2)
    user = command['user_id']
    username = command['user_name']
    arxiv_id = re.search(url_Reg, url).group(1)
    if new_for_user(arxiv_id, user) == 1:
        create_post(arxiv_id, user, username, '', comment)
    elif new_for_user(arxiv_id, user) == 2:
        add_new_input(arxiv_id, user, username, '', comment)
    else:
        rewrite_past_input(arxiv_id, user, username, '', comment)
    say("You have posted this url and your comments to the web page!")


@app.command("/comtag")
def comtag_command(ack, command, say):
    ack()
    match_obj = re.search(r"(.+)\s*(https://arxiv.org/abs/[\w.]+)\s*(.+)", command['text'])
    url = match_obj.group(2)
    tags = match_obj.group(1)
    comment = match_obj.group(3)
    user = command['user_id']
    username = command['user_name']
    arxiv_id = re.search(url_Reg, url).group(1)
    if new_for_user(arxiv_id, user) == 1:
        create_post(arxiv_id, user, username, tags, comment)
    elif new_for_user(arxiv_id, user) == 2:
        add_new_input(arxiv_id, user, username, tags, comment)
    else:
        rewrite_past_input(arxiv_id, user, username, tags, comment)
    say("You have posted this url,tags and your comments to the web page!")


if __name__ == "__main__":
    app.start(port=int(os.environ.get("PORT", 3000)))
