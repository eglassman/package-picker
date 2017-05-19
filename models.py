#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import logging
import datetime
import json
import copy
from peewee import Model, SqliteDatabase, Proxy, PostgresqlDatabase, \
    CharField, IntegerField, ForeignKeyField, DateTimeField, TextField, BooleanField


logger = logging.getLogger('data')

POSTGRES_CONFIG_NAME = 'postgres-credentials.json'
DATABASE_NAME = 'fetcher'
db_proxy = Proxy()


class BatchInserter(object):
    '''
    A class for saving database records in batches.
    Save rows to the batch inserter, and it will save the rows to
    the database after it has been given a batch size of rows.
    Make sure to call the `flush` method when you're finished using it
    to save any rows that haven't yet been saved.

    Assumes all models have been initialized to connect to db_proxy.
    '''
    def __init__(self, ModelType, batch_size, fill_missing_fields=False):
        '''
        ModelType is the Peewee model to which you want to save the data.
        If the rows you save will have fields missing for some of the records,
        set `fill_missing_fields` to true so that all rows will be augmented
        with all fields to prevent Peewee from crashing.
        '''
        self.rows = []
        self.ModelType = ModelType
        self.batch_size = batch_size
        self.pad_data = fill_missing_fields

    def insert(self, row):
        '''
        Save a row to the database.
        Each row is a dictionary of key-value pairs, where each key is the name of a field
        and each value is the value of the row for that column.
        '''
        self.rows.append(row)
        if len(self.rows) >= self.batch_size:
            self.flush()

    def flush(self):
        if self.pad_data:
            self._pad_data(self.rows)
        with db_proxy.atomic():
            self.ModelType.insert_many(self.rows).execute()
        self.rows = []

    def _pad_data(self, rows):
        '''
        Before we can bulk insert rows using Peewee, they all need to have the same
        fields.  This method adds the missing fields to all rows to make
        sure they all describe the same fields.  It does this destructively
        to the rows provided as input.
        '''
        # Collect the union of all field names
        field_names = set()
        for row in rows:
            field_names = field_names.union(row.keys())

        # We'll enforce that default for all unspecified fields is NULL
        default_data = {field_name: None for field_name in field_names}

        # Pad each row with the missing fields
        for i, _ in enumerate(rows):
            updated_data = copy.copy(default_data)
            updated_data.update(rows[i])
            rows[i] = updated_data


class ProxyModel(Model):
    ''' A peewee model that is connected to the proxy defined in this module. '''

    class Meta:
        database = db_proxy


class Seed(ProxyModel):
    ''' An initial query given by a user for which autocomplete results are shown. '''

    # Fetch logistics
    fetch_index = IntegerField(index=True)
    date = DateTimeField(index=True, default=datetime.datetime.now)

    # Data about the query
    parent = ForeignKeyField('self', null=True, related_name='children')
    seed = CharField()
    depth = IntegerField()


class Query(ProxyModel):
    ''' An instance of a suggestion returned in response to a seed query. '''

    # Fetch logistics
    fetch_index = IntegerField(index=True)
    date = DateTimeField(index=True, default=datetime.datetime.now)

    # Data about the query
    seed = ForeignKeyField(Seed)
    query = CharField()
    depth = IntegerField()
    rank = IntegerField()


class Search(ProxyModel):
    ''' A search query made to a search engine. '''

    fetch_index = IntegerField(index=True)
    date = DateTimeField(index=True, default=datetime.datetime.now)

    query = CharField()
    page_index = IntegerField()
    requested_count = IntegerField()
    result_count_on_page = IntegerField()
    estimated_results_count = IntegerField()

    # An optional field for associating a search with a specific package.
    # This should be specified whenever we need to trace a search to a related package.
    package = TextField(index=True, null=True)


class SearchResult(ProxyModel):
    ''' A result to a search query submitted to a search engine. '''

    search = ForeignKeyField(Search, related_name='results')
    title = TextField()
    snippet = TextField(null=True)
    link = CharField()
    url = CharField(index=True)
    updated_date = DateTimeField()
    rank = IntegerField()


class WebPageContent(ProxyModel):
    ''' The contents at a web URL at a point in time. '''

    date = DateTimeField(index=True, default=datetime.datetime.now)
    url = TextField(index=True)
    content = TextField()


class SearchResultContent(ProxyModel):
    ''' A link from search results to the content at the result's URL. '''

    search_result = ForeignKeyField(SearchResult)
    content = ForeignKeyField(WebPageContent)


class Code(ProxyModel):
    ''' A snippet of code found on a web page. '''

    # These fields signify when the snippet was extracted
    date = DateTimeField(index=True, default=datetime.datetime.now)
    compute_index = IntegerField(index=True)

    web_page = ForeignKeyField(WebPageContent)
    code = TextField()


class WebPageVersion(ProxyModel):
    '''
    A version of a web page at a URL as indexed by the Internet Archive.
    All fields beyond the URL are named based on their equivalent names in the Wayback
    Machine CDX API: https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server

    I believe they really mean the following, but have found no authoratative documents on this:
    * timestamp: the date and time this version of the page was crawled
    * original: the precise URL that was queried to find this page during the crawl
    * statuscode: the HTTP status code returned when this page was queried.  In some cases this
    *   might contain a 302 for a redirect.  I have also seen the value "-"
    * digest: a hash of the queried content.  (It might be that if two version share the same
    *   digest that they have the same content.)
    * length: size of the page in bytes
    '''

    # Fetch logistics
    fetch_index = IntegerField(index=True)
    date = DateTimeField(index=True, default=datetime.datetime.now)

    url = TextField(index=True)
    url_key = TextField()
    timestamp = DateTimeField(index=True)
    original = TextField()
    mime_type = TextField()
    # Status code is a text field as several test records we inspected had "-" for the status
    # instead of some integer value
    status_code = TextField(index=True)
    digest = TextField(index=True)
    length = IntegerField(null=True)


class QuestionSnapshot(ProxyModel):
    '''
    A snapshot of a Stack Overflow question at a moment when the API is queried.

    This contains much of the same data as the "Post" model.
    Though 'Snapshot' models come from periodic queries to the Stack Overflow API,
    rather than from a one-time data dump.  This allows us to describe the longitudinal change
    in Stack Overflow posts and data.
    '''

    # Fetch logistics
    fetch_index = IntegerField(index=True)
    date = DateTimeField(index=True, default=datetime.datetime.now)

    question_id = IntegerField(index=True)
    owner_id = IntegerField(null=True)
    comment_count = IntegerField()
    delete_vote_count = IntegerField()
    reopen_vote_count = IntegerField()
    close_vote_count = IntegerField()
    is_answered = BooleanField()
    view_count = IntegerField()
    favorite_count = IntegerField()
    down_vote_count = IntegerField()
    up_vote_count = IntegerField()
    answer_count = IntegerField()
    score = IntegerField()
    last_activity_date = DateTimeField()
    creation_date = DateTimeField()
    title = TextField()
    body = TextField()


class QuestionSnapshotTag(ProxyModel):
    ''' A link between one snapshot of a Stack Overflow question and one of its tags. '''
    # Both IDs are indexed to allow fast lookup of question snapshot for a given tag and vice versa.
    question_snapshot_id = IntegerField(index=True)
    tag_id = IntegerField(index=True)


class Post(ProxyModel):
    '''
    A post from Stack Overflow.

    For this schema and others for Stack Overflow data, we rely on the Stack Exchange
    data explorer to describe the types of each of the fields
    (see http://data.stackexchange.com/stackoverflow/query/new).

    Each of these models has an implicit "id" field that will correspond to
    its original ID in the Stack Overflow data dump.

    While some of fields refer to entries in other tables, we don't use indexes or
    foreign keys for the first iteration of these models.
    We don't yet know what queries we have to optimize for.

    I enabled some of the fields to be 'null' based on the ones that were not
    defined in a subset of the data to be imported.  It could be that other
    fields should be nullable that I haven't yet marked.

    For strings that require more than 255 bytes, we create TextFields.
    This is because the peewee reference states that CharFields are for storing
    "small strings (0-255 bytes)".
    We also store tinyints in IntegerFields.

    When setting the length for CharFields thar are supposed to store data
    that was originally "nvarchar", we double the count for the expected
    max_length, using the claim from raymondlewallen that nvarchar stored
    Unicode data, which needs two bytes per character:
    http://codebetter.com/raymondlewallen/2005/12/30/database-basics-quick-note-the-difference-in-varchar-and-nvarchar-data-types/
    '''
    # Default StackOverflow fields
    post_type_id = IntegerField()
    accepted_answer_id = IntegerField(null=True)
    parent_id = IntegerField(null=True)
    creation_date = DateTimeField()
    deletion_date = DateTimeField(null=True)
    score = IntegerField()
    view_count = IntegerField(null=True)
    body = TextField()
    owner_user_id = IntegerField(null=True)
    owner_display_name = CharField(max_length=80, null=True)
    last_editor_user_id = IntegerField(null=True)
    last_editor_display_name = CharField(max_length=80, null=True)
    last_edit_date = DateTimeField(null=True)
    last_activity_date = DateTimeField()
    title = TextField(null=True)
    tags = TextField(null=True)
    answer_count = IntegerField(null=True)
    comment_count = IntegerField()
    favorite_count = IntegerField(null=True)
    closed_date = DateTimeField(null=True)
    community_owned_date = DateTimeField(null=True)


class Tag(ProxyModel):
    ''' A tag for Stack Overflow posts. '''
    # We will look up tags based on their tag names when making PostTags
    tag_name = CharField(index=True, max_length=70)
    count = IntegerField()
    excerpt_post_id = IntegerField(index=True, null=True)
    wiki_post_id = IntegerField(null=True)


class PostHistory(ProxyModel):
    '''
    Some event related to a Stack Overflow post.

    'uniqueidentifier' is described to be a 16-byte GUID here:
    https://msdn.microsoft.com/en-us/library/ms187942.aspx
    So, we store the uniqueidentifier of the revision_guid field in a 16-byte character field.
    '''
    post_history_type_id = IntegerField()
    post_id = IntegerField()
    revision_guid = CharField(max_length=16)
    creation_date = DateTimeField()
    user_id = IntegerField(null=True)
    user_display_name = CharField(max_length=80, null=True)
    comment = TextField(null=True)
    text = TextField()


class PostLink(ProxyModel):
    ''' Link between Stack Overflow posts. '''
    creation_date = DateTimeField()
    post_id = IntegerField()
    related_post_id = IntegerField()
    link_type_id = IntegerField()


class Vote(ProxyModel):
    ''' A vote on a Stack Overflow post. '''
    post_id = IntegerField()
    vote_type_id = IntegerField()
    user_id = IntegerField(null=True)
    creation_date = DateTimeField()
    bounty_amount = IntegerField(null=True)


class Comment(ProxyModel):
    ''' Comment on a Stack Overflow post. '''
    post_id = IntegerField()
    score = IntegerField()
    text = TextField()
    creation_date = DateTimeField()
    user_display_name = CharField(max_length=60, null=True)
    user_id = IntegerField(null=True)


class Badge(ProxyModel):
    ''' Badge assigned to a Stack Overflow user. '''
    user_id = IntegerField()
    name = CharField(max_length=100)
    date = DateTimeField()
    class_ = IntegerField()
    tag_based = BooleanField()


class User(ProxyModel):
    ''' User on Stack Overflow. '''
    reputation = IntegerField()
    creation_date = DateTimeField()
    display_name = CharField(max_length=80)
    last_access_date = DateTimeField()
    website_url = TextField(null=True)
    location = CharField(max_length=200, null=True)
    about_me = TextField(null=True)
    views = IntegerField()
    up_votes = IntegerField()
    down_votes = IntegerField()
    profile_image_url = TextField(null=True)
    email_hash = CharField(max_length=32, null=True)
    age = IntegerField(null=True)
    account_id = IntegerField()


class PostTag(ProxyModel):
    ''' A link between a Stack Overflow post and one of its tags. '''
    # Both IDs are indexed to allow fast lookup of posts for a given tag and vice versa.
    post_id = IntegerField(index=True)
    tag_id = IntegerField(index=True)


class SnippetPattern(ProxyModel):
    ''' A regular expression pattern describing a rule for detecting a snippet. '''
    pattern = TextField(index=True)


class PostSnippet(ProxyModel):
    ''' A snippet of code found in a Stack Overflow post. '''
    compute_index = IntegerField(index=True)
    date = DateTimeField(index=True, default=datetime.datetime.now)
    post = ForeignKeyField(Post)
    pattern = ForeignKeyField(SnippetPattern)
    snippet = TextField()


class PostNpmInstallPackage(ProxyModel):
    ''' A package referenced in an 'npm install' command in a Stack Overflow post. '''
    compute_index = IntegerField(index=True)
    date = DateTimeField(index=True, default=datetime.datetime.now)
    post = ForeignKeyField(Post)
    package = TextField()


class Task(ProxyModel):
    ''' A task that describes what you can do with a software package. '''
    compute_index = IntegerField(index=True)
    date = DateTimeField(index=True, default=datetime.datetime.now)
    task = TextField(index=True)
    mode = TextField(index=True)
    search_result_content = ForeignKeyField(SearchResultContent, index=True)


class Verb(ProxyModel):
    ''' A lemmatized verb that found in programming documentation. '''
    verb = TextField(index=True)


class Noun(ProxyModel):
    ''' A lemmatized noun that found in programming documentation. '''
    noun = TextField(index=True)


class TaskVerb(ProxyModel):
    ''' A link that connects a verb to a task description it was discovered in. '''
    task = ForeignKeyField(Task, index=True)
    verb = ForeignKeyField(Verb, index=True)


class TaskNoun(ProxyModel):
    ''' A link that connects a noun to a task description it was discovered in. '''
    task = ForeignKeyField(Task, index=True)
    noun = ForeignKeyField(Noun, index=True)


class GitHubProject(ProxyModel):
    ''' A project on GitHub. '''

    # Fetch logistics
    fetch_index = IntegerField(index=True)
    date = DateTimeField(index=True, default=datetime.datetime.now)

    # These identifiers identify the project from different contexts.
    # 'name' will give the name of a package that has a GitHub project.
    # 'owner' and 'repo' uniquely identify a GitHub project and provide
    # the URL through which we reach it in the API.
    name = TextField(index=True)
    owner = TextField()
    repo = TextField()


class Issue(ProxyModel):
    '''
    An issue for a GitHub project.
    The 'body' field is nullable as we found during our initial fetch that some
    of the issues data contained 'null' bodies.
    '''

    # Fetch logistics
    fetch_index = IntegerField(index=True)
    date = DateTimeField(index=True, default=datetime.datetime.now)

    github_id = IntegerField()
    project = ForeignKeyField(GitHubProject)

    # Fields from the GitHub API
    number = IntegerField()
    created_at = DateTimeField(index=True)
    updated_at = DateTimeField(index=True)
    closed_at = DateTimeField(index=True, null=True)
    state = TextField()
    body = TextField(null=True)
    comments = IntegerField()
    user_id = IntegerField(index=True, null=True, default=None)


class IssueEvent(ProxyModel):
    ''' An event (e.g., "closed") for an issue for a GitHub project. '''

    fetch_index = IntegerField(index=True)
    date = DateTimeField(index=True, default=datetime.datetime.now)

    github_id = IntegerField()
    issue = ForeignKeyField(Issue)
    created_at = DateTimeField(index=True)
    event = TextField()


class IssueComment(ProxyModel):
    ''' A comment on a GitHub issue. '''

    fetch_index = IntegerField(index=True)
    date = DateTimeField(index=True, default=datetime.datetime.now)

    github_id = IntegerField()
    issue = ForeignKeyField(Issue)
    created_at = DateTimeField(index=True)
    updated_at = DateTimeField(index=True)
    body = TextField()
    user_id = IntegerField(index=True, null=True, default=None)


class SlantTopic(ProxyModel):
    ''' A topic of discussion on the Slant website. '''

    fetch_index = IntegerField(index=True)
    date = DateTimeField(index=True, default=datetime.datetime.now)

    topic_id = IntegerField(index=True)
    title = TextField()
    # For now, the endpoint we call only provides paths relative to an unnamed host,
    # so this field only contains the path of the URL
    url_path = TextField()
    owner_username = TextField()


class Viewpoint(ProxyModel):
    ''' A "viewpoint" or alternative suggested in responts to a question on Slant. '''

    fetch_index = IntegerField(index=True)
    date = DateTimeField(index=True, default=datetime.datetime.now)

    topic = ForeignKeyField(SlantTopic)
    viewpoint_index = IntegerField()
    title = TextField()
    # Similarly to SlantTopic, only the URL path is provided, without domain
    url_path = TextField()


class ViewpointSection(ProxyModel):
    ''' A pro / con section describing a viewpoint or alternative on Slant. '''

    fetch_index = IntegerField(index=True)
    date = DateTimeField(index=True, default=datetime.datetime.now)

    viewpoint = ForeignKeyField(Viewpoint)
    section_index = IntegerField()
    title = TextField()
    text = TextField()
    is_con = BooleanField()
    upvotes = IntegerField()
    downvotes = IntegerField()


def init_database(db_type, config_filename=None):

    if db_type == 'postgres':

        # If the user wants to use Postgres, they should define their credentials
        # in an external config file, which are used here to access the database.
        config_filename = config_filename if config_filename else POSTGRES_CONFIG_NAME
        with open(config_filename) as pg_config_file:
            pg_config = json.load(pg_config_file)

        config = {}
        config['user'] = pg_config['dbusername']
        if 'dbpassword' in pg_config:
            config['password'] = pg_config['dbpassword']
        if 'host' in pg_config:
            config['host'] = pg_config['host']

        db = PostgresqlDatabase(DATABASE_NAME, **config)

    # Sqlite is the default type of database.
    elif db_type == 'sqlite' or not db_type:
        db = SqliteDatabase(DATABASE_NAME + '.db')

    db_proxy.initialize(db)


def create_tables():
    db_proxy.create_tables([
        Query,
        Seed,
        Search,
        SearchResult,
        WebPageContent,
        Code,
        SearchResultContent,
        WebPageVersion,
        QuestionSnapshot,
        QuestionSnapshotTag,
        Post,
        Tag,
        PostHistory,
        PostLink,
        Vote,
        Comment,
        Badge,
        User,
        PostTag,
        SnippetPattern,
        PostSnippet,
        PostNpmInstallPackage,
        Task,
        TaskNoun,
        TaskVerb,
        Noun,
        Verb,
        GitHubProject,
        Issue,
        IssueComment,
        IssueEvent,
        SlantTopic,
        Viewpoint,
        ViewpointSection,
    ], safe=True)
