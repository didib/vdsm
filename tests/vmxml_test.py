# -*- coding: utf-8 -*-
#
# Copyright 2014-2017 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#
from __future__ import absolute_import
from __future__ import print_function

import os.path
import re
import timeit
import xml.etree.ElementTree as etree

from vdsm.common import cpuarch
from vdsm.virt import domain_descriptor
from vdsm.virt import vmchannels
from vdsm.virt import vmxml
# TODO: split those tests as well
from vdsm.virt import libvirtxml


from testValidation import brokentest, slowtest
from testlib import VdsmTestCase as TestCaseBase
from testlib import XMLTestCase, permutations, expandPermutations

import vmfakelib as fake

from vmTestsData import CONF_TO_DOMXML_X86_64
from vmTestsData import CONF_TO_DOMXML_PPC64
from vmTestsData import CONF_TO_DOMXML_NO_VDSM


class VmXmlTestCase(TestCaseBase):

    _CONFS = {
        cpuarch.X86_64: CONF_TO_DOMXML_X86_64,
        cpuarch.PPC64: CONF_TO_DOMXML_PPC64,
        'novdsm': CONF_TO_DOMXML_NO_VDSM}

    def _build_domain_xml(self, arch):
        for conf, rawXml in self._CONFS[arch]:
            domXml = rawXml % conf
            yield fake.Domain(domXml, vmId=conf['vmId']), domXml


@expandPermutations
class TestVmXmlFunctions(VmXmlTestCase):

    @permutations([[cpuarch.X86_64], [cpuarch.PPC64]])
    def test_has_channel(self, arch):
        for _, dom_xml in self._build_domain_xml(arch):
            self.assertEqual(True, vmxml.has_channel(
                dom_xml, vmchannels.LEGACY_DEVICE_NAME))

    @permutations([
        # custom, mapping
        [{}, {}],
        [{'volumeMap': 'data:vda'}, {'data': 'vda'}],
        [{'volumeMap': 'data:vda,extra:vdb'},
         {'data': 'vda', 'extra': 'vdb'}],
        [{'volumeMap': 'data1:vda, data2:vdb'},
         {'data1': 'vda', 'data2': 'vdb'}],
    ])
    def test_parse_drive_mapping(self, custom, mapping):
        result = libvirtxml.parse_drive_mapping(custom)
        self.assertEqual(result, mapping)

    @permutations([
        # custom, exc
        [{'volumeMap': ''}, ValueError],
        [{'volumeMap': 'foobar'}, ValueError],
    ])
    def test_explode_parsing_drive_mapping(self, custom, exc):
        self.assertRaises(exc,
                          libvirtxml.parse_drive_mapping,
                          custom)


@expandPermutations
class TestVmXmlHelpers(XMLTestCase):

    _XML = u'''<?xml version="1.0" ?>
    <topelement>
      <hello lang="english">hello</hello>
      <hello cyrillic="yes" lang="русский">здра́вствуйте</hello>
      <bye>good bye<hello lang="čeština">dobrý den</hello></bye>
      <container><subelement/></container>
      <container><subelement>some content</subelement></container>
      <empty/>
    </topelement>
    '''

    def setUp(self):
        self._dom = vmxml.parse_xml(self._XML)

    def test_import_export(self):
        xml = vmxml.format_xml(self._dom)
        self.assertXMLEqual(xml, self._XML)

    def test_pretty_format_formatting(self):
        xml = re.sub(' *\n *', '', self._XML)
        dom = vmxml.parse_xml(xml)
        pretty = vmxml.format_xml(dom, pretty=True)
        self.assertEqual(pretty, '''<?xml version='1.0' encoding='utf-8'?>
<topelement>
    <hello lang="english">hello</hello>
    <hello cyrillic="yes" lang="русский">здра́вствуйте</hello>
    <bye>good bye<hello lang="čeština">dobrý den</hello>
    </bye>
    <container>
        <subelement />
    </container>
    <container>
        <subelement>some content</subelement>
    </container>
    <empty />
</topelement>
''')

    def test_pretty_format_safety(self):
        # Check that dom is not modified in format_xml; we check that by
        # comparing the exported forms of `dom' created before and after
        # format_xml call.
        xml = re.sub(' *\n *', '', self._XML)
        dom = vmxml.parse_xml(xml)
        exported_1 = etree.tostring(dom)
        vmxml.format_xml(dom, pretty=True)
        exported_2 = etree.tostring(dom)
        self.assertEqual(exported_1, exported_2)

    @slowtest
    def test_pretty_format_timing(self):
        test_path = os.path.realpath(__file__)
        dir_name = os.path.split(test_path)[0]
        xml_path = os.path.join(dir_name, 'devices', 'data',
                                'testComplexVm.xml')
        xml = re.sub(' *\n *', '', open(xml_path).read())
        setup = """
import re
from vdsm.virt import vmxml
xml = re.sub(' *\\n *', '', '''%s''')
dom = vmxml.parse_xml(xml)
def run():
    vmxml.format_xml(dom, pretty=%%s)""" % (xml,)
        repetitions = 100
        elapsed = timeit.timeit('run()', setup=(setup % ('False',)),
                                number=repetitions)
        elapsed_pretty = timeit.timeit('run()', setup=(setup % ('True',)),
                                       number=repetitions)
        print('slowdown: %d%% (%.3f s per one domain)' %
              (100 * (elapsed_pretty - elapsed) / elapsed,
               (elapsed_pretty - elapsed) / repetitions,))

    @permutations([[None, 'topelement', 1],
                   ['topelement', 'topelement', 1],
                   [None, 'hello', 3],
                   ['topelement', 'bye', 1],
                   [None, 'none', 0]])
    def test_find_all(self, start_tag, tag, number):
        dom = self._dom
        if start_tag is not None:
            dom = vmxml.find_first(self._dom, 'topelement')
        elements = vmxml.find_all(dom, tag)
        matches = [vmxml.tag(e) == tag for e in elements]
        self.assertTrue(all(matches))
        self.assertEqual(len(matches), number)

    def test_find_first_not_found(self):
        self.assertRaises(vmxml.NotFound, vmxml.find_first, self._dom, 'none')

    @permutations([['hello', 'lang', 'english'],
                   ['hello', 'none', ''],
                   ['none', 'lang', ''],
                   ])
    def test_find_attr(self, tag, attribute, result):
        value = vmxml.find_attr(self._dom, tag, attribute)
        self.assertEqual(value, result)

    @permutations([['hello', 1, {'cyrillic': 'yes', 'lang': 'русский'}],
                   ['topelement', 0, {}],
                   ['empty', 0, {}],
                   ])
    def test_attributes(self, tag, index, result):
        element = list(vmxml.find_all(self._dom, tag))[index]
        self.assertEqual(vmxml.attributes(element), result)

    @permutations([['hello', 'hello'],
                   ['empty', '']])
    def test_text(self, tag, result):
        element = vmxml.find_first(self._dom, tag)
        text = vmxml.text(element)
        self.assertEqual(text, result)

    @permutations([['topelement', 'hello', 2],
                   ['bye', 'hello', 1],
                   ['empty', 'hello', 0],
                   ['topelement', 'none', 0],
                   ['topelement', None, 6],
                   ])
    def test_children(self, start_tag, tag, number):
        element = vmxml.find_first(self._dom, start_tag)
        self.assertEqual(len(list(vmxml.children(element, tag))), number)

    def test_append_child(self):
        empty = vmxml.find_first(self._dom, 'empty')
        vmxml.append_child(empty, vmxml.Element('new'))
        self.assertIsNotNone(vmxml.find_first(self._dom, 'new', None))
        empty = vmxml.find_first(self._dom, 'empty')
        self.assertIsNotNone(vmxml.find_first(empty, 'new', None))

    def test_append_child_etree(self):
        empty = vmxml.find_first(self._dom, 'empty')
        vmxml.append_child(empty, etree_child=vmxml.parse_xml('<new/>'))
        self.assertIsNotNone(vmxml.find_first(self._dom, 'new', None))
        empty = vmxml.find_first(self._dom, 'empty')
        self.assertIsNotNone(vmxml.find_first(empty, 'new', None))

    def test_append_child_noargs(self):
        empty = vmxml.find_first(self._dom, 'empty')
        self.assertRaises(RuntimeError, vmxml.append_child, empty)

    def test_append_child_too_many_args(self):
        empty = vmxml.find_first(self._dom, 'empty')
        self.assertRaises(RuntimeError, vmxml.append_child, empty,
                          vmxml.Element('new'),
                          vmxml.parse_xml('<new/>'))

    def test_remove_child(self):
        top = vmxml.find_first(self._dom, 'topelement')
        hello = list(vmxml.find_all(top, 'hello'))
        old = hello[1]
        vmxml.remove_child(top, old)
        updated_hello = list(vmxml.find_all(top, 'hello'))
        hello = hello[:1] + hello[2:]
        self.assertEqual(updated_hello, hello)

    def test_replace_child(self):
        expected = '''<topelement>
    <hello lang="english">hello</hello>
    <hello cyrillic="yes" lang="русский">здра́вствуйте</hello>
    <bye>good bye<hello lang="čeština">dobrý den</hello>
    </bye>
    <container>
        <foo>
            <bar>baz</bar>
        </foo>
    </container>
    <container>
        <subelement>some content</subelement>
    </container>
    <empty />
</topelement>
'''
        new_element = '<foo><bar>baz</bar></foo>'
        new_child = vmxml.parse_xml(new_element)
        container = vmxml.find_first(self._dom, 'container')
        vmxml.replace_first_child(container, new_child)
        self.assertXMLEqual(vmxml.format_xml(self._dom, pretty=True), expected)

    def test_namespaces(self):
        expected_xml = '''
        <domain xmlns:ovirt-tune="http://ovirt.org/vm/tune/1.0">
          <metadata>
            <ovirt-tune:qos/>
          </metadata>
        </domain>
        '''
        domain = vmxml.Element('domain')
        metadata = vmxml.Element('metadata')
        domain.appendChild(metadata)
        qos = vmxml.Element('qos', namespace='ovirt-tune',
                            namespace_uri='http://ovirt.org/vm/tune/1.0')
        metadata.appendChild(qos)
        self.assertXMLEqual(vmxml.format_xml(domain), expected_xml)

    @brokentest('find_first returns the innermost nested element')
    def test_find_first_nested(self):
        XML = u'''<?xml version="1.0" ?>
        <topelement>
          <subelement id="1">
              <subelement id="2"/>
          </subelement>
        </topelement>
        '''
        dom = vmxml.parse_xml(XML)
        sub1 = vmxml.find_first(dom, 'subelement')  # outermost
        sub2 = vmxml.find_first(sub1, 'subelement')  # innermost
        last = vmxml.find_first(sub2, 'subelement')
        self.assertIsNot(sub2, last)


@expandPermutations
class TestDomainDescriptor(VmXmlTestCase):

    @permutations([[domain_descriptor.DomainDescriptor, cpuarch.X86_64],
                   [domain_descriptor.DomainDescriptor, cpuarch.PPC64],
                   [domain_descriptor.MutableDomainDescriptor, cpuarch.X86_64]]
                  )
    def test_all_channels_vdsm_domain(self, descriptor, arch):
        for _, dom_xml in self._build_domain_xml(arch):
            dom = descriptor(dom_xml)
            channels = list(dom.all_channels())
            self.assertTrue(len(channels) >=
                            len(vmchannels.AGENT_DEVICE_NAMES))
            for name, path in channels:
                self.assertIn(name, vmchannels.AGENT_DEVICE_NAMES)

    @permutations([[domain_descriptor.DomainDescriptor],
                   [domain_descriptor.MutableDomainDescriptor]])
    def test_all_channels_extra_domain(self, descriptor):
        for conf, raw_xml in CONF_TO_DOMXML_NO_VDSM:
            dom = descriptor(raw_xml % conf)
            self.assertNotEquals(sorted(dom.all_channels()),
                                 sorted(vmchannels.AGENT_DEVICE_NAMES))

    def test_no_channels(self):
        dom = domain_descriptor.MutableDomainDescriptor('<domain/>')
        self.assertEqual(list(dom.all_channels()), [])


@expandPermutations
class TestVmXmlMetadata(XMLTestCase):

    def __init__(self, *args, **kwargs):
        XMLTestCase.__init__(self, *args, **kwargs)
        self.channelListener = None
        self.conf = {
            'vmName': 'testVm',
            'vmId': '9ffe28b6-6134-4b1e-8804-1185f49c436f',
            'smp': '8',
            'maxVCpus': '160',
            'memSize': '1024',
            'memGuaranteedSize': '512',
        }

    def test_no_custom(self):
        expected = """
          <domain type="kvm"
                  xmlns:ovirt-tune="http://ovirt.org/vm/tune/1.0"
                  xmlns:ovirt-vm="http://ovirt.org/vm/1.0">
            <metadata>
              <ovirt-tune:qos/>
              <ovirt-vm:vm/>
            </metadata>
          </domain>
        """
        conf = {}
        conf.update(self.conf)
        domxml = StrippedDomain(conf, self.log, cpuarch.X86_64)
        domxml.appendMetadata()
        result = domxml.toxml()
        self.assertXMLEqual(result, expected)

    @permutations([
        # conf
        [{}],
        [{'custom': {}}],
        [{'custom': {'containerImage': 'foobar'}}],
        [{'custom': {'containerType': 'foobar'}}],
    ])
    def test_no_container_data(self, conf):
        expected = """
          <domain type="kvm"
                  xmlns:ovirt-tune="http://ovirt.org/vm/tune/1.0"
                  xmlns:ovirt-vm="http://ovirt.org/vm/1.0">
            <metadata>
              <ovirt-tune:qos/>
              <ovirt-vm:vm/>
            </metadata>
          </domain>
        """
        conf.update(self.conf)
        domxml = StrippedDomain(conf, self.log, cpuarch.X86_64)
        domxml.appendMetadata()
        result = domxml.toxml()
        self.assertXMLEqual(result, expected)

    def test_container_data(self):
        expected = """
          <domain xmlns:ns0="http://ovirt.org/vm/tune/1.0"
                  xmlns:ns1="http://ovirt.org/vm/1.0"
                  xmlns:ns2="http://ovirt.org/vm/containers/1.0"
                  type="kvm">
            <metadata>
              <ns0:qos />
              <ns1:vm/>
              <ns2:container>
                <ns2:image>foobar</ns2:image>
                <ns2:runtime>foobar</ns2:runtime>
              </ns2:container>
            </metadata>
          </domain>
        """
        conf = {
            'custom': {
                'containerImage': 'foobar',
                'containerType': 'foobar',
            }
        }
        conf.update(self.conf)
        domxml = StrippedDomain(conf, self.log, cpuarch.X86_64)
        domxml.appendMetadata()
        result = domxml.toxml()
        self.assertXMLEqual(result, expected)

    def test_container_data_drive_map(self):
        expected = """
          <domain xmlns:ns0="http://ovirt.org/vm/tune/1.0"
                  xmlns:ns1="http://ovirt.org/vm/1.0"
                  xmlns:ns2="http://ovirt.org/vm/containers/1.0"
                  xmlns:ns3="http://ovirt.org/vm/containers/drivemap/1.0"
                  type="kvm">
            <metadata>
              <ns0:qos />
              <ns1:vm/>
              <ns2:container>
                <ns2:image>foobar</ns2:image>
                <ns2:runtime>foobar</ns2:runtime>
              </ns2:container>
              <ns3:drivemap>
                <ns3:data1>vda</ns3:data1>
                <ns3:data2>vdb</ns3:data2>
              </ns3:drivemap>
            </metadata>
          </domain>
        """
        conf = {
            'custom': {
                'containerImage': 'foobar',
                'containerType': 'foobar',
                'volumeMap': 'data1:vda,data2:vdb',
            }
        }
        conf.update(self.conf)
        domxml = StrippedDomain(conf, self.log, cpuarch.X86_64)
        domxml.appendMetadata()
        result = domxml.toxml()
        self.assertXMLEqual(result, expected)


class StrippedDomain(libvirtxml.Domain):
    """
    Bare-bones libvirtxml.Domain, which doesn't add elements on its __init__
    to sinmplify the testing. Will be dropped if libvirtxml.Domain
    is refactored.
    """
    def __init__(self, conf, log, arch):
        self.conf = conf
        self.log = log
        self.arch = arch
        self.dom = vmxml.Element('domain', type='kvm')

    def toxml(self):
        return vmxml.format_xml(self.dom)
