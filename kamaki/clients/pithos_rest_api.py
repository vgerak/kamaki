# Copyright 2011-2012 GRNET S.A. All rights reserved.
#
# Redistribution and use in source and binary forms, with or
# without modification, are permitted provided that the following
# conditions are met:
#
#   1. Redistributions of source code must retain the above
#      copyright notice, this list of conditions and the following
#      disclaimer.
#
#   2. Redistributions in binary form must reproduce the above
#      copyright notice, this list of conditions and the following
#      disclaimer in the documentation and/or other materials
#      provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY GRNET S.A. ``AS IS'' AND ANY EXPRESS
# OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL GRNET S.A OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF
# USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and
# documentation are those of the authors and should not be
# interpreted as representing official policies, either expressed
# or implied, of GRNET S.A.

from .storage import StorageClient, ClientError
from .utils import path4url, list2str

class PithosRestAPI(StorageClient):

    def account_head(self, until = None,
        if_modified_since=None, if_unmodified_since=None, *args, **kwargs):
        """ Full Pithos+ HEAD at account level
        --- request parameters ---
        @param until (string): optional timestamp
        --- --- optional request headers ---
        @param if_modified_since (string): Retrieve if account has changed since provided timestamp
        @param if_unmodified_since (string): Retrieve if account has not changed since provided timestamp
        """
        self.assert_account()
        path = path4url(self.account)

        self.set_param('until', until, iff = until is not None)
        self.set_header('If-Modified-Since', if_modified_since)
        self.set_header('If-Unmodified-Since', if_unmodified_since)

        success = kwargs.pop('success', 204)
        return self.head(path, *args, success=success, **kwargs)

    def account_get(self, limit=None, marker=None, format='json', show_only_shared=False, until=None,
        if_modified_since=None, if_unmodified_since=None, *args, **kwargs):
        """  Full Pithos+ GET at account level
        --- request parameters ---
        @param limit (integer): The amount of results requested (server will use default value if None)
        @param marker (string): Return containers with name lexicographically after marker
        @param format (string): reply format can be json or xml (default: json)
        @param shared (bool): If true, only shared containers will be included in results
        @param until (string): optional timestamp
        --- --- optional request headers ---
        @param if_modified_since (string): Retrieve if account has changed since provided timestamp
        @param if_unmodified_since (string): Retrieve if account has not changed since provided timestamp
        """
        self.assert_account()

        self.set_param('format',format, iff = format is not None)
        self.set_param('limit',limit, iff = limit is not None)
        self.set_param('marker',marker, iff = marker is not None)
        self.set_param('shared', iff = show_only_shared)
        self.set_param('until',until, iff = until is not None)

        self.set_header('If-Modified-Since', if_modified_since)
        self.set_header('If-Unmodified-Since', if_unmodified_since)

        path = path4url(self.account)
        success = kwargs.pop('success', (200, 204))
        return self.get(path, *args, success = success, **kwargs)

    def account_post(self, update=True,
        groups={}, metadata=None, quota=None, versioning=None, *args, **kwargs):
        """ Full Pithos+ POST at account level
        --- request parameters ---
        @param update (bool): if True, Do not replace metadata/groups
        --- request headers ---
        @groups (dict): Optional user defined groups in the form
                    {   'group1':['user1', 'user2', ...], 
                        'group2':['userA', 'userB', ...], ...
                    }
        @metadata (dict): Optional user defined metadata in the form
                    {   'name1': 'value1',
                        'name2': 'value2', ...
                    }
        @param quota(integer): If supported, sets the Account quota
        @param versioning(string): If supported, sets the Account versioning
                    to 'auto' or some other supported versioning string
        """
        self.assert_account()

        self.set_param('update', iff = update)

        for group, usernames in groups.items():
            userstr = ''
            dlm = ''
            for user in usernames:
                userstr = userstr + dlm + user
                dlm = ','
            self.set_header('X-Account-Group-'+group, userstr)
        if metadata is not None:
            for metaname, metaval in metadata.items():
                self.set_header('X-Account-Meta-'+metaname, metaval)
        self.set_header('X-Account-Policy-Quota', quota)
        self.set_header('X-Account-Policy-Versioning', versioning)

        path = path4url(self.account)
        success = kwargs.pop('success', 202)
        return self.post(path, *args, success=success, **kwargs)

    def container_head(self, until=None,
        if_modified_since=None, if_unmodified_since=None, *args, **kwargs):
        """ Full Pithos+ HEAD at container level
        --- request params ---
        @param until (string): optional timestamp
        --- optional request headers --- 
        @param if_modified_since (string): Retrieve if account has changed since provided timestamp
        @param if_unmodified_since (string): Retrieve if account has not changed since provided timestamp
        """
        self.assert_container()

        self.set_param('until', until, iff=until is not None)

        self.set_header('If-Modified-Since', if_modified_since)
        self.set_header('If-Unmodified-Since', if_unmodified_since)

        path = path4url(self.account, self.container)
        success = kwargs.pop('success', 204)
        return self.head(path, *args, success=success, **kwargs)

    def container_get(self, limit = None, marker = None, prefix=None, delimiter=None, path = None,
        format='json', meta=[], show_only_shared=False, until=None,
        if_modified_since=None, if_unmodified_since=None, *args, **kwargs):
        """ Full Pithos+ GET at container level
        --- request parameters ---
        @param limit (integer): The amount of results requested (server qill use default value if None)
        @param marker (string): Return containers with name lexicographically after marker
        @param prefix (string): Return objects starting with prefix
        @param delimiter (string): Return objects up to the delimiter
        @param path (string): assume prefix = path and delimiter = / (overwrites prefix
        and delimiter)
        @param format (string): reply format can be json or xml (default: json)
        @param meta (list): Return objects that satisfy the key queries in the specified
        comma separated list (use <key>, !<key> for existence queries, <key><op><value>
        for value queries, where <op> can be one of =, !=, <=, >=, <, >)
        @param shared (bool): If true, only shared containers will be included in results
        @param until (string): optional timestamp
        --- --- optional request headers ---
        @param if_modified_since (string): Retrieve if account has changed since provided timestamp
        @param if_unmodified_since (string): Retrieve if account has not changed since provided timestamp
        """
        self.assert_container()

        self.set_param('format', format, iff=format is not None)
        self.set_param('limit', limit, iff=limit is not None)
        self.set_param('marker', marker, iff=marker is not None)
        if path is None:
            self.set_param('prefix', prefix, iff=prefix is not None)
            self.set_param('delimiter', delimiter, iff=delimiter is not None)
        else:
            self.set_param('path', path)
        self.set_param('shared', iff=show_only_shared)
        self.set_param('meta', list2str(meta), iff=meta is not None and len(meta) > 0)
        self.set_param('until', until, iff=until is not None)

        self.set_header('If-Modified-Since', if_modified_since)
        self.set_header('If-Unmodified-Since', if_unmodified_since)

        path = path4url(self.account, self.container)
        success = kwargs.pop('success', 200)
        return self.get(path, *args, success=success, **kwargs)

    def container_put(self, quota=None, versioning=None, metadata=None, *args, **kwargs):
        """ Full Pithos+ PUT at container level
        --- request headers ---
        @param quota (integer): Size limit in KB
        @param versioning (string): 'auto' or other string supported by server
        @metadata (dict): Optional user defined metadata in the form
        {   'name1': 'value1',
        'name2': 'value2', ...
        }
        """
        self.assert_container()

        if metadata is not None:
            for metaname, metaval in metadata.items():
                self.set_header('X-Container-Meta-'+metaname, metaval)
        self.set_header('X-Container-Policy-Quota', quota)
        self.set_header('X-Container-Policy-Versioning', versioning)

        path = path4url(self.account, self.container)
        success = kwargs.pop('success',(201, 202))
        return self.put(path, *args, success=success, **kwargs)

    def container_post(self, update=True, format='json',
        quota=None, versioning=None, metadata=None, content_type=None, content_length=None,
        transfer_encoding=None, *args, **kwargs):
        """ Full Pithos+ POST at container level
        --- request params ---
        @param update (bool):  if True, Do not replace metadata/groups
        @param format(string): json (default) or xml
        --- request headers ---
        @param quota (integer): Size limit in KB
        @param versioning (string): 'auto' or other string supported by server
        @metadata (dict): Optional user defined metadata in the form
        {   'name1': 'value1',
        'name2': 'value2', ...
        }
        @param content_type (string): set a custom content type
        @param content_length (string): set a custrom content length
        @param transfer_encoding (string): set a custrom transfer encoding
        """
        self.assert_container()

        self.set_param('format', format, iff=format is not None)
        self.set_param('update', iff=update)

        if metadata is not None:
            for metaname, metaval in metadata.items():
                self.set_header('X-Container-Meta-'+metaname, metaval)
        self.set_header('X-Container-Policy-Quota', quota)
        self.set_header('X-Container-Policy-Versioning', versioning)
        self.set_header('Content-Type', content_type)
        self.set_header('Content-Length', content_length)
        self.set_header('Transfer-Encoding', transfer_encoding)

        path = path4url(self.account, self.container)
        success = kwargs.pop('success', 202)
        return self.post(path, *args, success=success, **kwargs)

    def container_delete(self, until=None, delimiter=None, *args, **kwargs):
        """ Full Pithos+ DELETE at container level
        --- request parameters ---
        @param until (timestamp string): if defined, container is purged up to that time
        """
        self.assert_container()        

        self.set_param('until', until, iff=until is not None)
        self.set_param('delimiter', delimiter, iff=delimiter is not None)

        path=path4url(self.account, self.container)
        success = kwargs.pop('success', 204)
        return self.delete(path, success=success)

    def object_head(self, object, version=None, if_etag_match=None, if_etag_not_match = None,
        if_modified_since = None, if_unmodified_since = None, *args, **kwargs):
        """ Full Pithos+ HEAD at object level
        --- request parameters ---
        @param version (string): optional version identified
        --- request headers ---
        @param if_etag_match (string): if provided, return only results
                with etag matching with this
        @param if_etag_not_match (string): if provided, return only results
                with etag not matching with this
        @param if_modified_since (string): Retrieve if account has changed since provided timestamp
        @param if_unmodified_since (string): Retrieve if account has not changed since provided timestamp
        """
        self.assert_container()

        self.set_param('version', version, iff=version is not None)

        self.set_header('If-Match', if_etag_match)
        self.set_header('If-None-Match', if_etag_not_match)
        self.set_header('If-Modified-Since', if_modified_since)
        self.set_header('If-Unmodified-Since', if_unmodified_since)

        path=path4url(self.account, self.container, object)
        success = kwargs.pop('success', 200)
        return self.head(path, *args, success=success, **kwargs)

    def object_get(self, object, format='json', hashmap=False, version=None,
        data_range=None, if_range=False, if_etag_match=None, if_etag_not_match = None,
        if_modified_since = None, if_unmodified_since = None, *args, **kwargs):
        """ Full Pithos+ GET at object level
        --- request parameters ---
        @param format (string): json (default) or xml
        @param hashmap (bool): Optional request for hashmap
        @param version (string): optional version identified
        --- request headers ---
        @param data_range (string): Optional range of data to retrieve
        @param if_range (bool): 
        @param if_etag_match (string): if provided, return only results
                with etag matching with this
        @param if_etag_not_match (string): if provided, return only results
                with etag not matching with this
        @param if_modified_since (string): Retrieve if account has changed since provided timestamp
        @param if_unmodified_since (string): Retrieve if account has not changed since provided timestamp
        """
        self.assert_container()

        self.set_param('format', format, iff=format is not None)
        self.set_param('version', version, iff=version is not None)
        self.set_param('hashmap', hashmap, iff=hashmap)

        self.set_header('Range', data_range)
        self.set_header('If-Range', '', if_range is True and data_range is not None)
        self.set_header('If-Match', if_etag_match, )
        self.set_header('If-None-Match', if_etag_not_match)
        self.set_header('If-Modified-Since', if_modified_since)
        self.set_header('If-Unmodified-Since', if_unmodified_since)

        path=path4url(self.account, self.container, object)
        success = kwargs.pop('success', 200)
        return self.get(path, *args, success=success, **kwargs)

    def object_put(self, object, format='json', hashmap=False, delimiter = None, if_etag_match=None,
        if_etag_not_match = None, etag=None, content_length = None, content_type=None,
        transfer_encoding=None, copy_from=None, move_from=None, source_account=None,
        source_version=None, content_encoding = None, content_disposition=None, manifest = None,
        permitions =None, public = None, metadata=None, *args, **kwargs):
        """ Full Pithos+ PUT at object level
        --- request parameters ---
        @param format (string): json (default) or xml
        @param hashmap (bool): Optional hashmap provided instead of data
        --- request headers ---
        @param if_etag_match (string): if provided, return only results
                with etag matching with this
        @param if_etag_not_match (string): if provided, return only results
                with etag not matching with this
        @param etag (string): The MD5 hash of the object (optional to check written data)
        @param content_length (integer): The size of the data written
        @param content_type (string): The MIME content type of the object
        @param transfer_encoding (string): Set to chunked to specify incremental uploading (if used, Content-Length is ignored)
        @param copy_from (string): The source path in the form /<container>/<object>
        @param move_from (string): The source path in the form /<container>/<object>
        @param source_account (string): The source account to copy/move from
        @param source_version (string): The source version to copy from
        @param conent_encoding (string): The encoding of the object
        @param content_disposition (string): The presentation style of the object
        @param manifest (string): Object parts prefix in /<container>/<object> form
        @param permitions (dict): Object permissions in the form (all fields are optional)
                {'read':[user1, group1, user2, ...], 'write':['user3, group2, group3, ...]}
        @param public (bool): If true, Object is publicly accessible, if false, not
        @param metadata (dict): Optional user defined metadata in the form
                {'meta-key-1':'meta-value-1', 'meta-key-2':'meta-value-2', ...}
        """
        self.assert_container()

        self.set_param('format', format, iff=format is not None)
        self.set_param('hashmap', hashmap, iff=hashmap)
        self.set_param('delimiter', delimiter, iff=delimiter is not None)

        self.set_header('If-Match', if_etag_match)
        self.set_header('If-None-Match', if_etag_not_match)
        self.set_header('ETag', etag)
        self.set_header('Content-Length', content_length)
        self.set_header('Content-Type', content_type)
        self.set_header('Transfer-Encoding', transfer_encoding)
        self.set_header('X-Copy-From', copy_from)
        self.set_header('X-Move-From', move_from)
        self.set_header('X-Source-Account', source_account)
        self.set_header('X-Source-Version', source_version)
        self.set_header('Content-Encoding', content_encoding)
        self.set_header('Content-Disposition', content_disposition)
        self.set_header('X-Object-Manifest', manifest)
        perms = None
        if permitions is not None:
            for permition_type, permition_list in permitions.items():
                if perms is None:
                    perms = '' #Remove permitions
                if len(permition_list) == 0:
                    continue
                perms += ';'+permition_type if len(perms) > 0 else permition_type
                perms += '='+list2str(permition_list, seperator=',')
        self.set_header('X-Object-Sharing', perms)
        self.set_header('X-Object-Public', public)
        if metadata is not None:
            for key, val in metadata.items():
                self.set_header('X-Object-Meta-'+key, val)

        path=path4url(self.account, self.container, object)
        success = kwargs.pop('success', 201)
        return self.put(path, *args, success=success, **kwargs)

    def object_copy(self, object, destination, format='json', ignore_content_type=False,
        if_etag_match=None, if_etag_not_match=None, destination_account=None,
        content_type=None, content_encoding=None, content_disposition=None, source_version=None,
        permitions=None, public=False, metadata=None, *args, **kwargs):
        """ Full Pithos+ COPY at object level
        --- request parameters ---
        @param format (string): json (default) or xml
        @param ignore_content_type (bool): Ignore the supplied Content-Type
        --- request headers ---
         @param if_etag_match (string): if provided, copy only results
                with etag matching with this
        @param if_etag_not_match (string): if provided, copy only results
                with etag not matching with this
        @param destination (string): The destination path in the form /<container>/<object>
        @param destination_account (string): The destination account to copy to
        @param content_type (string): The MIME content type of the object
        @param content_encoding (string): The encoding of the object
        @param content_disposition (string): The presentation style of the object
        @param source_version (string): The source version to copy from
        @param permitions (dict): Object permissions in the form (all fields are optional)
                {'read':[user1, group1, user2, ...], 'write':['user3, group2, group3, ...]}
                permitions override source permitions, removing any old permitions
        @param public (bool): If true, Object is publicly accessible, if else, not
        @param metadata (dict): Optional user defined metadata in the form
                {'meta-key-1':'meta-value-1', 'meta-key-2':'meta-value-2', ...}
                Metadata are appended to the source metadata. In case of same keys, they
                replace the old metadata
        """
        self.assert_container()

        self.set_param('format', format, iff=format is not None)
        self.set_param('ignore_content_type', iff=ignore_content_type)

        self.set_header('If-Match', if_etag_match)
        self.set_header('If-None-Match', if_etag_not_match)
        self.set_header('Destination', destination)
        self.set_header('Destination-Account', destination_account)
        self.set_header('Content-Type', content_type)
        self.set_header('Content-Encoding', content_encoding)
        self.set_header('Content-Disposition', content_disposition)
        self.set_header('X-Source-Version', source_version)
        perms = None
        if permitions is not None:
            for permition_type, permition_list in permitions.items():
                if perms is None:
                    perms = '' #Remove permitions
                if len(permition_list) == 0:
                    continue
                perms += ';'+permition_type if len(perms) > 0 else permition_type
                perms += '='+list2str(permition_list, seperator=',')
        self.set_header('X-Object-Sharing', perms)
        self.set_header('X-Object-Public', public)
        if metadata is not None:
            for key, val in metadata.items():
                self.set_header('X-Object-Meta-'+key, val)

        path = path4url(self.account, self.container, object)
        success = kwargs.pop('success', 201)
        return self.copy(path, *args, success=success, **kwargs)

    def object_move(self, object, format='json', ignore_content_type=False,
        if_etag_match=None, if_etag_not_match=None, destination=None, destination_account=None,
        content_type=None, content_encoding=None, content_disposition=None, permitions={},
        public=False, metadata={}, *args, **kwargs):
        """ Full Pithos+ COPY at object level
        --- request parameters ---
        @param format (string): json (default) or xml
        @param ignore_content_type (bool): Ignore the supplied Content-Type
        --- request headers ---
         @param if_etag_match (string): if provided, return only results
                with etag matching with this
        @param if_etag_not_match (string): if provided, return only results
                with etag not matching with this
        @param destination (string): The destination path in the form /<container>/<object>
        @param destination_account (string): The destination account to copy to
        @param content_type (string): The MIME content type of the object
        @param content_encoding (string): The encoding of the object
        @param content_disposition (string): The presentation style of the object
        @param source_version (string): The source version to copy from
        @param permitions (dict): Object permissions in the form (all fields are optional)
                {'read':[user1, group1, user2, ...], 'write':['user3, group2, group3, ...]}
        @param public (bool): If true, Object is publicly accessible, if false, not
        @param metadata (dict): Optional user defined metadata in the form
                {'meta-key-1':'meta-value-1', 'meta-key-2':'meta-value-2', ...}
        """
        self.assert_container()

        self.set_param('format', format, iff=format is not None)
        self.set_param('ignore_content_type', iff=ignore_content_type)

        self.set_header('If-Match', if_etag_match)
        self.set_header('If-None-Match', if_etag_not_match)
        self.set_header('Destination', destination)
        self.set_header('Destination-Account', destination_account)
        self.set_header('Content-Type', content_type)
        self.set_header('Content-Encoding', content_encoding)
        self.set_header('Content-Disposition', content_disposition)
        perms = None
        for permition_type, permition_list in permitions.items():
            if perms is None:
                perms = '' #Remove permitions
            if len(permition_list) == 0:
                continue
            perms += ';'+permition_type if len(perms) > 0 else permition_type
            perms += '='+list2str(permition_list, seperator=',')
        self.set_header('X-Object-Sharing', perms)
        self.set_header('X-Object-Public', public)
        for key, val in metadata.items():
            self.set_header('X-Object-Meta-'+key, val)

        path = path4url(self.account, self.container, object)
        success = kwargs.pop('success', 201)
        return self.move(path, *args, success=success, **kwargs)

    def object_post(self, object, format='json', update=True,
        if_etag_match=None, if_etag_not_match=None, content_length=None, content_type=None,
        content_range=None, transfer_encoding=None, content_encoding=None, content_disposition=None,
        source_object=None, source_account=None, source_version=None, object_bytes=None,
        manifest=None, permitions={}, public=False, metadata={}, *args, **kwargs):
        """ Full Pithos+ POST at object level
        --- request parameters ---
        @param format (string): json (default) or xml
        @param update (bool): Do not replace metadata
        --- request headers ---
        @param if_etag_match (string): if provided, return only results
                with etag matching with this
        @param if_etag_not_match (string): if provided, return only results
                with etag not matching with this
        @param content_length (string): The size of the data written
        @param content_type (string): The MIME content type of the object
        @param content_range (string): The range of data supplied
        @param transfer_encoding (string): Set to chunked to specify incremental uploading
                (if used, Content-Length is ignored)
        @param content_encoding (string): The encoding of the object
        @param content_disposition (string): The presentation style of the object
        @param source_object (string): Update with data from the object at path /<container>/<object>
        @param source_account (string): The source account to update from
        @param source_version (string): The source version to copy from
        @param object_bytes (integer): The updated objects final size
        @param manifest (string): Object parts prefix in /<container>/<object> form
        @param permitions (dict): Object permissions in the form (all fields are optional)
                {'read':[user1, group1, user2, ...], 'write':['user3, group2, group3, ...]}
        @param public (bool): If true, Object is publicly accessible, if false, not
        @param metadata (dict): Optional user defined metadata in the form
                {'meta-key-1':'meta-value-1', 'meta-key-2':'meta-value-2', ...}
        """
        self.assert_container()

        self.set_param('format', format, iff=format is not None)
        self.set_param('update', iff = update)

        self.set_header('If-Match', if_etag_match)
        self.set_header('If-None-Match', if_etag_not_match)
        self.set_header('Content-Length', content_length, iff=transfer_encoding is None)
        self.set_header('Content-Type', content_type)
        self.set_header('Content-Range', content_range)
        self.set_header('Transfer-Encoding', transfer_encoding)
        self.set_header('Content-Encoding', content_encoding)
        self.set_header('Content-Disposition', content_disposition)
        self.set_header('X-Source-Object', source_object)
        self.set_header('X-Source-Account', source_account)
        self.set_header('X-Source-Version', source_version)
        self.set_header('X-Object-Bytes', object_bytes)
        self.set_header('X-Object-Manifest', manifest)
        perms = None
        for permition_type, permition_list in permitions.items():
            if perms is None:
                perms = '' #Remove permitions
            if len(permition_list) == 0:
                continue
            perms += ';'+permition_type if len(perms) > 0 else permition_type
            perms += '='+list2str(permition_list, seperator=',')
        self.set_header('X-Object-Sharing', perms)
        self.set_header('X-Object-Public', public)
        for key, val in metadata.items():
            self.set_header('X-Object-Meta-'+key, val)

        path = path4url(self.account, self.container, object)
        success=kwargs.pop('success', (202, 204))
        return self.post(path, *args, success=success, **kwargs)
       
    def object_delete(self, object, until=None, delimiter=None, *args, **kwargs):
        """ Full Pithos+ DELETE at object level
        --- request parameters --- 
        @param until (string): Optional timestamp
        """
        self.assert_container()

        self.set_param('until', until, iff=until is not None)
        self.set_param('delimiter', delimiter, iff=delimiter is not None)

        path = path4url(self.account, self.container, object)
        success = kwargs.pop('success', 204)
        return self.delete(path, *args, success=success, **kwargs)