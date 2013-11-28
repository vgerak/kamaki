# Copyright 2012-2013 GRNET S.A. All rights reserved.
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
# or implied, of GRNET S.A.command

from json import load, dumps
from os import path
from logging import getLogger
from io import StringIO
from pydoc import pager

from kamaki.cli import command
from kamaki.cli.command_tree import CommandTree
from kamaki.cli.utils import filter_dicts_by_dict
from kamaki.clients.image import ImageClient
from kamaki.clients.pithos import PithosClient
from kamaki.clients.astakos import AstakosClient
from kamaki.clients import ClientError
from kamaki.cli.argument import (
    FlagArgument, ValueArgument, RepeatableArgument, KeyValueArgument,
    IntArgument, ProgressBarArgument)
from kamaki.cli.commands.cyclades import _init_cyclades
from kamaki.cli.errors import raiseCLIError, CLIBaseUrlError
from kamaki.cli.commands import _command_init, errors, addLogSettings
from kamaki.cli.commands import (
    _optional_output_cmd, _optional_json, _name_filter, _id_filter)


image_cmds = CommandTree('image', 'Cyclades/Plankton API image commands')
imagecompute_cmds = CommandTree(
    'imagecompute', 'Cyclades/Compute API image commands')
_commands = [image_cmds, imagecompute_cmds]


howto_image_file = [
    'Kamaki commands to:',
    ' get current user id: /user authenticate',
    ' check available containers: /file list',
    ' create a new container: /file create <container>',
    ' check container contents: /file list <container>',
    ' upload files: /file upload <image file> <container>',
    ' register an image: /image register <image name> <container>:<path>']

about_image_id = ['To see a list of available image ids: /image list']


log = getLogger(__name__)


class _init_image(_command_init):
    @errors.generic.all
    @addLogSettings
    def _run(self):
        if getattr(self, 'cloud', None):
            img_url = self._custom_url('image') or self._custom_url('plankton')
            if img_url:
                token = self._custom_token('image') or self._custom_token(
                    'plankton') or self.config.get_cloud(self.cloud, 'token')
                self.client = ImageClient(base_url=img_url, token=token)
                return
        if getattr(self, 'auth_base', False):
            plankton_endpoints = self.auth_base.get_service_endpoints(
                self._custom_type('image') or self._custom_type(
                    'plankton') or 'image',
                self._custom_version('image') or self._custom_version(
                    'plankton') or '')
            base_url = plankton_endpoints['publicURL']
            token = self.auth_base.token
        else:
            raise CLIBaseUrlError(service='plankton')
        self.client = ImageClient(base_url=base_url, token=token)

    def main(self):
        self._run()


# Plankton Image Commands


def _validate_image_meta(json_dict, return_str=False):
    """
    :param json_dict" (dict) json-formated, of the form
        {"key1": "val1", "key2": "val2", ...}

    :param return_str: (boolean) if true, return a json dump

    :returns: (dict) if return_str is not True, else return str

    :raises TypeError, AttributeError: Invalid json format

    :raises AssertionError: Valid json but invalid image properties dict
    """
    json_str = dumps(json_dict, indent=2)
    for k, v in json_dict.items():
        if k.lower() == 'properties':
            for pk, pv in v.items():
                prop_ok = not (isinstance(pv, dict) or isinstance(pv, list))
                assert prop_ok, 'Invalid property value for key %s' % pk
                key_ok = not (' ' in k or '-' in k)
                assert key_ok, 'Invalid property key %s' % k
            continue
        meta_ok = not (isinstance(v, dict) or isinstance(v, list))
        assert meta_ok, 'Invalid value for meta key %s' % k
        meta_ok = ' ' not in k
        assert meta_ok, 'Invalid meta key [%s]' % k
        json_dict[k] = '%s' % v
    return json_str if return_str else json_dict


def _load_image_meta(filepath):
    """
    :param filepath: (str) the (relative) path of the metafile

    :returns: (dict) json_formated

    :raises TypeError, AttributeError: Invalid json format

    :raises AssertionError: Valid json but invalid image properties dict
    """
    with open(path.abspath(filepath)) as f:
        meta_dict = load(f)
        try:
            return _validate_image_meta(meta_dict)
        except AssertionError:
            log.debug('Failed to load properties from file %s' % filepath)
            raise


def _validate_image_location(location):
    """
    :param location: (str) pithos://<user-id>/<container>/<image-path>

    :returns: (<user-id>, <container>, <image-path>)

    :raises AssertionError: if location is invalid
    """
    prefix = 'pithos://'
    msg = 'Invalid prefix for location %s , try: %s' % (location, prefix)
    assert location.startswith(prefix), msg
    service, sep, rest = location.partition('://')
    assert sep and rest, 'Location %s is missing user-id' % location
    uuid, sep, rest = rest.partition('/')
    assert sep and rest, 'Location %s is missing container' % location
    container, sep, img_path = rest.partition('/')
    assert sep and img_path, 'Location %s is missing image path' % location
    return uuid, container, img_path


@command(image_cmds)
class image_list(_init_image, _optional_json, _name_filter, _id_filter):
    """List images accessible by user"""

    PERMANENTS = (
        'id', 'name',
        'status', 'container_format', 'disk_format', 'size')

    arguments = dict(
        detail=FlagArgument('show detailed output', ('-l', '--details')),
        container_format=ValueArgument(
            'filter by container format',
            '--container-format'),
        disk_format=ValueArgument('filter by disk format', '--disk-format'),
        size_min=IntArgument('filter by minimum size', '--size-min'),
        size_max=IntArgument('filter by maximum size', '--size-max'),
        status=ValueArgument('filter by status', '--status'),
        owner=ValueArgument('filter by owner', '--owner'),
        owner_name=ValueArgument('filter by owners username', '--owner-name'),
        order=ValueArgument(
            'order by FIELD ( - to reverse order)',
            '--order',
            default=''),
        limit=IntArgument('limit number of listed images', ('-n', '--number')),
        more=FlagArgument(
            'output results in pages (-n to set items per page, default 10)',
            '--more'),
        enum=FlagArgument('Enumerate results', '--enumerate'),
        prop=KeyValueArgument('filter by property key=value', ('--property')),
        prop_like=KeyValueArgument(
            'fliter by property key=value where value is part of actual value',
            ('--property-like')),
        image_ID_for_members=ValueArgument(
            'List members of an image', '--members-of')
    )

    def _filter_by_owner(self, images):
        ouuid = self['owner'] or self._username2uuid(self['owner_name'])
        return filter_dicts_by_dict(images, dict(owner=ouuid))

    def _add_owner_name(self, images):
        uuids = self._uuids2usernames(
            list(set([img['owner'] for img in images])))
        for img in images:
            img['owner'] += ' (%s)' % uuids[img['owner']]
        return images

    def _filter_by_properties(self, images):
        new_images = []
        for img in images:
            props = [dict(img['properties'])]
            if self['prop']:
                props = filter_dicts_by_dict(props, self['prop'])
            if props and self['prop_like']:
                props = filter_dicts_by_dict(
                    props, self['prop_like'], exact_match=False)
            if props:
                new_images.append(img)
        return new_images

    def _members(self, image_id):
        members = self.client.list_members(image_id)
        if not (self['json_output'] or self['output_format']):
            uuids = [member['member_id'] for member in members]
            usernames = self._uuids2usernames(uuids)
            for member in members:
                member['member_id'] += ' (%s)' % usernames[member['member_id']]
        self._print(members, title=('member_id',))

    @errors.generic.all
    @errors.cyclades.connection
    def _run(self):
        super(self.__class__, self)._run()
        if self['image_ID_for_members']:
            return self._members(self['image_ID_for_members'])
        filters = {}
        for arg in set([
                'container_format',
                'disk_format',
                'name',
                'size_min',
                'size_max',
                'status']).intersection(self.arguments):
            filters[arg] = self[arg]

        order = self['order']
        detail = self['detail'] or (
            self['prop'] or self['prop_like']) or (
            self['owner'] or self['owner_name'])

        images = self.client.list_public(detail, filters, order)

        if self['owner'] or self['owner_name']:
            images = self._filter_by_owner(images)
        if self['prop'] or self['prop_like']:
            images = self._filter_by_properties(images)
        images = self._filter_by_id(images)
        images = self._non_exact_name_filter(images)

        if self['detail'] and not (
                self['json_output'] or self['output_format']):
            images = self._add_owner_name(images)
        elif detail and not self['detail']:
            for img in images:
                for key in set(img).difference(self.PERMANENTS):
                    img.pop(key)
        kwargs = dict(with_enumeration=self['enum'])
        if self['limit']:
            images = images[:self['limit']]
        if self['more']:
            kwargs['out'] = StringIO()
            kwargs['title'] = ()
        self._print(images, **kwargs)
        if self['more']:
            pager(kwargs['out'].getvalue())

    def main(self):
        super(self.__class__, self)._run()
        self._run()


@command(image_cmds)
class image_info(_init_image, _optional_json):
    """Get image metadata"""

    @errors.generic.all
    @errors.plankton.connection
    @errors.plankton.id
    def _run(self, image_id):
        meta = self.client.get_meta(image_id)
        if not (self['json_output'] or self['output_format']):
            meta['owner'] += ' (%s)' % self._uuid2username(meta['owner'])
        self._print(meta, self.print_dict)

    def main(self, image_id):
        super(self.__class__, self)._run()
        self._run(image_id=image_id)


@command(image_cmds)
class image_modify(_init_image, _optional_output_cmd):
    """Add / update metadata and properties for an image
    The original image preserves the values that are not affected
    """

    arguments = dict(
        image_name=ValueArgument('Change name', '--name'),
        disk_format=ValueArgument('Change disk format', '--disk-format'),
        container_format=ValueArgument(
            'Change container format', '--container-format'),
        status=ValueArgument('Change status', '--status'),
        publish=FlagArgument('Publish the image', '--publish'),
        unpublish=FlagArgument('Unpublish the image', '--unpublish'),
        property_to_set=KeyValueArgument(
            'set property in key=value form (can be repeated)',
            ('-p', '--property-set')),
        property_to_del=RepeatableArgument(
            'Delete property by key (can be repeated)', '--property-del'),
        member_ID_to_add=RepeatableArgument(
            'Add member to image (can be repeated)', '--member-add'),
        member_ID_to_remove=RepeatableArgument(
            'Remove a member (can be repeated)', '--member-del'),
    )
    required = [
        'image_name', 'disk_format', 'container_format', 'status', 'publish',
        'unpublish', 'property_to_set', 'member_ID_to_add',
        'member_ID_to_remove']

    @errors.generic.all
    @errors.plankton.connection
    @errors.plankton.id
    def _run(self, image_id):
        for mid in self['member_ID_to_add']:
            self.client.add_member(image_id, mid)
        for mid in self['member_ID_to_remove']:
            self.client.remove_member(image_id, mid)
        if len([term for term in self.required if (
                self[term] and not term.startswith('member_ID'))]) > 1:
            meta = self.client.get_meta(image_id)
            for k, v in self['property_to_set'].items():
                meta['properties'][k.upper()] = v
            for k in self['property_to_del']:
                meta['properties'][k.upper()] = None
            self._optional_output(self.client.update_image(
                image_id,
                name=self['image_name'],
                disk_format=self['disk_format'],
                container_format=self['container_format'],
                status=self['status'],
                public=self['publish'] or self['unpublish'] or None,
                **meta['properties']))
        if self['with_output']:
            self._optional_output(self.get_image_details(image_id))

    def main(self, image_id):
        super(self.__class__, self)._run()
        self._run(image_id=image_id)


@command(image_cmds)
class image_register(_init_image, _optional_json):
    """(Re)Register an image file to an Image service
    The image file must be stored at a pithos repository
    Some metadata can be set by user (e.g., disk-format) while others are set
    only automatically (e.g., image id). There are also some custom user
    metadata, called properties.
    A register command creates a remote meta file at
    .  <container>:<image path>.meta
    Users may download and edit this file and use it to re-register one or more
    images.
    In case of a meta file, runtime arguments for metadata or properties
    override meta file settings.
    """

    container_info_cache = {}

    arguments = dict(
        checksum=ValueArgument('Set image checksum', '--checksum'),
        container_format=ValueArgument(
            'Set container format', '--container-format'),
        disk_format=ValueArgument('Set disk format', '--disk-format'),
        owner_name=ValueArgument('Set user uuid by user name', '--owner-name'),
        properties=KeyValueArgument(
            'Add property (user-specified metadata) in key=value form'
            '(can be repeated)',
            ('-p', '--property')),
        is_public=FlagArgument('Mark image as public', '--public'),
        size=IntArgument('Set image size in bytes', '--size'),
        metafile=ValueArgument(
            'Load metadata from a json-formated file <img-file>.meta :'
            '{"key1": "val1", "key2": "val2", ..., "properties: {...}"}',
            ('--metafile')),
        metafile_force=FlagArgument(
            'Overide remote metadata file', ('-f', '--force')),
        no_metafile_upload=FlagArgument(
            'Do not store metadata in remote meta file',
            ('--no-metafile-upload')),
        container=ValueArgument(
            'Pithos+ container containing the image file',
            ('-C', '--container')),
        uuid=ValueArgument('Custom user uuid', '--uuid'),
        local_image_path=ValueArgument(
            'Local image file path to upload and register '
            '(still need target file in the form container:remote-path )',
            '--upload-image-file'),
        progress_bar=ProgressBarArgument(
            'Do not use progress bar', '--no-progress-bar', default=False)
    )

    def _get_user_id(self):
        atoken = self.client.token
        if getattr(self, 'auth_base', False):
            return self.auth_base.term('id', atoken)
        else:
            astakos_url = self.config.get('user', 'url') or self.config.get(
                'astakos', 'url')
            if not astakos_url:
                raise CLIBaseUrlError(service='astakos')
            user = AstakosClient(astakos_url, atoken)
            return user.term('id')

    def _get_pithos_client(self, container):
        if self['no_metafile_upload']:
            return None
        ptoken = self.client.token
        if getattr(self, 'auth_base', False):
            pithos_endpoints = self.auth_base.get_service_endpoints(
                'object-store')
            purl = pithos_endpoints['publicURL']
        else:
            purl = self.config.get_cloud('pithos', 'url')
        if not purl:
            raise CLIBaseUrlError(service='pithos')
        return PithosClient(purl, ptoken, self._get_user_id(), container)

    def _store_remote_metafile(self, pclient, remote_path, metadata):
        return pclient.upload_from_string(
            remote_path, _validate_image_meta(metadata, return_str=True),
            container_info_cache=self.container_info_cache)

    def _load_params_from_file(self, location):
        params, properties = dict(), dict()
        pfile = self['metafile']
        if pfile:
            try:
                for k, v in _load_image_meta(pfile).items():
                    key = k.lower().replace('-', '_')
                    if key == 'properties':
                        for pk, pv in v.items():
                            properties[pk.upper().replace('-', '_')] = pv
                    elif key == 'name':
                            continue
                    elif key == 'location':
                        if location:
                            continue
                        location = v
                    else:
                        params[key] = v
            except Exception as e:
                raiseCLIError(e, 'Invalid json metadata config file')
        return params, properties, location

    def _load_params_from_args(self, params, properties):
        for key in set([
                'checksum',
                'container_format',
                'disk_format',
                'owner',
                'size',
                'is_public']).intersection(self.arguments):
            params[key] = self[key]
        for k, v in self['properties'].items():
            properties[k.upper().replace('-', '_')] = v

    def _validate_location(self, location):
        if not location:
            raiseCLIError(
                'No image file location provided',
                importance=2, details=[
                    'An image location is needed. Image location format:',
                    '  <container>:<path>',
                    ' where an image file at the above location must exist.'
                    ] + howto_image_file)
        try:
            return _validate_image_location(location)
        except AssertionError as ae:
            raiseCLIError(
                ae, 'Invalid image location format',
                importance=1, details=[
                    'Valid image location format:',
                    '  <container>:<img-file-path>'
                    ] + howto_image_file)

    @staticmethod
    def _old_location_format(location):
        prefix = 'pithos://'
        try:
            if location.startswith(prefix):
                uuid, sep, rest = location[len(prefix):].partition('/')
                container, sep, path = rest.partition('/')
                return (uuid, container, path)
        except Exception as e:
            raiseCLIError(e, 'Invalid location format', details=[
                'Correct location format:', '  <container>:<image path>'])
        return ()

    def _mine_location(self, container_path):
        old_response = self._old_location_format(container_path)
        if old_response:
            return old_response
        uuid = self['uuid'] or (self._username2uuid(self['owner_name']) if (
                    self['owner_name']) else self._get_user_id())
        if not uuid:
            if self['owner_name']:
                raiseCLIError('No user with username %s' % self['owner_name'])
            raiseCLIError('Failed to get user uuid', details=[
                'For details on current user:',
                '  /user whoami',
                'To authenticate a new user through a user token:',
                '  /user authenticate <token>'])
        if self['container']:
            return uuid, self['container'], container_path
        container, sep, path = container_path.partition(':')
        if not (bool(container) and bool(path)):
            raiseCLIError(
                'Incorrect container-path format', importance=1, details=[
                'Use : to seperate container form path',
                '  <container>:<image-path>',
                'OR',
                'Use -C to specifiy a container',
                '  -C <container> <image-path>'] + howto_image_file)

        return uuid, container, path

    @errors.generic.all
    @errors.plankton.connection
    @errors.pithos.container
    def _run(self, name, uuid, dst_cont, img_path):
        if self['local_image_path']:
            with open(self['local_image_path']) as f:
                pithos = self._get_pithos_client(dst_cont)
                (pbar, upload_cb) = self._safe_progress_bar('Uploading')
                if pbar:
                    hash_bar = pbar.clone()
                    hash_cb = hash_bar.get_generator('Calculating hashes')
                pithos.upload_object(
                    img_path, f,
                    hash_cb=hash_cb, upload_cb=upload_cb,
                    container_info_cache=self.container_info_cache)
                pbar.finish()

        location = 'pithos://%s/%s/%s' % (uuid, dst_cont, img_path)
        (params, properties, new_loc) = self._load_params_from_file(location)
        if location != new_loc:
            uuid, dst_cont, img_path = self._validate_location(new_loc)
        self._load_params_from_args(params, properties)
        pclient = self._get_pithos_client(dst_cont)

        #check if metafile exists
        meta_path = '%s.meta' % img_path
        if pclient and not self['metafile_force']:
            try:
                pclient.get_object_info(meta_path)
                raiseCLIError(
                    'Metadata file %s:%s already exists, abort' % (
                        dst_cont, meta_path),
                    details=['Registration ABORTED', 'Try -f to overwrite'])
            except ClientError as ce:
                if ce.status != 404:
                    raise

        #register the image
        try:
            r = self.client.register(name, location, params, properties)
        except ClientError as ce:
            if ce.status in (400, 404):
                raiseCLIError(
                    ce, 'Nonexistent image file location\n\t%s' % location,
                    details=[
                        'Does the image file %s exist at container %s ?' % (
                            img_path, dst_cont)] + howto_image_file)
            raise
        r['owner'] += ' (%s)' % self._uuid2username(r['owner'])
        self._print(r, self.print_dict)

        #upload the metadata file
        if pclient:
            try:
                meta_headers = pclient.upload_from_string(
                    meta_path, dumps(r, indent=2),
                    container_info_cache=self.container_info_cache)
            except TypeError:
                self.error(
                    'Failed to dump metafile %s:%s' % (dst_cont, meta_path))
                return
            if self['json_output'] or self['output_format']:
                self.print_json(dict(
                    metafile_location='%s:%s' % (dst_cont, meta_path),
                    headers=meta_headers))
            else:
                self.error('Metadata file uploaded as %s:%s (version %s)' % (
                    dst_cont, meta_path, meta_headers['x-object-version']))

    def main(self, name, container___image_path):
        super(self.__class__, self)._run()
        self._run(name, *self._mine_location(container___image_path))


@command(image_cmds)
class image_unregister(_init_image, _optional_output_cmd):
    """Unregister an image (does not delete the image file)"""

    @errors.generic.all
    @errors.plankton.connection
    @errors.plankton.id
    def _run(self, image_id):
        self._optional_output(self.client.unregister(image_id))

    def main(self, image_id):
        super(self.__class__, self)._run()
        self._run(image_id=image_id)


# Compute Image Commands

@command(imagecompute_cmds)
class imagecompute_list(
        _init_cyclades, _optional_json, _name_filter, _id_filter):
    """List images"""

    PERMANENTS = ('id', 'name')

    arguments = dict(
        detail=FlagArgument('show detailed output', ('-l', '--details')),
        limit=IntArgument('limit number listed images', ('-n', '--number')),
        more=FlagArgument('handle long lists of results', '--more'),
        enum=FlagArgument('Enumerate results', '--enumerate'),
        user_id=ValueArgument('filter by user_id', '--user-id'),
        user_name=ValueArgument('filter by username', '--user-name'),
        meta=KeyValueArgument(
            'filter by metadata key=value (can be repeated)', ('--metadata')),
        meta_like=KeyValueArgument(
            'filter by metadata key=value (can be repeated)',
            ('--metadata-like'))
    )

    def _filter_by_metadata(self, images):
        new_images = []
        for img in images:
            meta = [dict(img['metadata'])]
            if self['meta']:
                meta = filter_dicts_by_dict(meta, self['meta'])
            if meta and self['meta_like']:
                meta = filter_dicts_by_dict(
                    meta, self['meta_like'], exact_match=False)
            if meta:
                new_images.append(img)
        return new_images

    def _filter_by_user(self, images):
        uuid = self['user_id'] or self._username2uuid(self['user_name'])
        return filter_dicts_by_dict(images, dict(user_id=uuid))

    def _add_name(self, images, key='user_id'):
        uuids = self._uuids2usernames(
            list(set([img[key] for img in images])))
        for img in images:
            img[key] += ' (%s)' % uuids[img[key]]
        return images

    @errors.generic.all
    @errors.cyclades.connection
    def _run(self):
        withmeta = bool(self['meta'] or self['meta_like'])
        withuser = bool(self['user_id'] or self['user_name'])
        detail = self['detail'] or withmeta or withuser
        images = self.client.list_images(detail)
        images = self._filter_by_name(images)
        images = self._filter_by_id(images)
        if withuser:
            images = self._filter_by_user(images)
        if withmeta:
            images = self._filter_by_metadata(images)
        if self['detail'] and not (
                self['json_output'] or self['output_format']):
            images = self._add_name(self._add_name(images, 'tenant_id'))
        elif detail and not self['detail']:
            for img in images:
                for key in set(img).difference(self.PERMANENTS):
                    img.pop(key)
        kwargs = dict(with_enumeration=self['enum'])
        if self['limit']:
            images = images[:self['limit']]
        if self['more']:
            kwargs['out'] = StringIO()
            kwargs['title'] = ()
        self._print(images, **kwargs)
        if self['more']:
            pager(kwargs['out'].getvalue())

    def main(self):
        super(self.__class__, self)._run()
        self._run()


@command(imagecompute_cmds)
class imagecompute_info(_init_cyclades, _optional_json):
    """Get detailed information on an image"""

    @errors.generic.all
    @errors.cyclades.connection
    @errors.plankton.id
    def _run(self, image_id):
        image = self.client.get_image_details(image_id)
        uuids = [image['user_id'], image['tenant_id']]
        usernames = self._uuids2usernames(uuids)
        image['user_id'] += ' (%s)' % usernames[image['user_id']]
        image['tenant_id'] += ' (%s)' % usernames[image['tenant_id']]
        self._print(image, self.print_dict)

    def main(self, image_id):
        super(self.__class__, self)._run()
        self._run(image_id=image_id)


@command(imagecompute_cmds)
class imagecompute_delete(_init_cyclades, _optional_output_cmd):
    """Delete an image (WARNING: image file is also removed)"""

    @errors.generic.all
    @errors.cyclades.connection
    @errors.plankton.id
    def _run(self, image_id):
        self._optional_output(self.client.delete_image(image_id))

    def main(self, image_id):
        super(self.__class__, self)._run()
        self._run(image_id=image_id)


@command(imagecompute_cmds)
class imagecompute_modify(_init_cyclades, _optional_output_cmd):
    """Modify image properties (metadata)"""

    arguments = dict(
        property_to_add=KeyValueArgument(
            'Add property in key=value format (can be repeated)',
            ('--property-add')),
        property_to_del=RepeatableArgument(
            'Delete property by key (can be repeated)',
            ('--property-del'))
    )
    required = ['property_to_add', 'property_to_del']

    @errors.generic.all
    @errors.cyclades.connection
    @errors.plankton.id
    def _run(self, image_id):
        if self['property_to_add']:
            self.client.update_image_metadata(
                image_id, **self['property_to_add'])
        for key in self['property_to_del']:
            self.client.delete_image_metadata(image_id, key)
        if self['with_output']:
            self._optional_output(self.client.get_image_details(image_id))

    def main(self, image_id):
        super(self.__class__, self)._run()
        self._run(image_id=image_id)
