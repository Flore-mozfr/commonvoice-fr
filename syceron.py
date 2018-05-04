#!/usr/bin/env python3

import sys
import re
import os
import argparse
import networkx as nx
import networkx.drawing.nx_pydot as nx_pydot
import datetime

from xml.dom.pulldom import START_ELEMENT, CHARACTERS, END_ELEMENT, parse
from xml.dom.minidom import Element, Text

parser = argparse.ArgumentParser(description='SyceronBrut text content extraction for Common Voice')
parser.add_argument('--debug', action='store_true', default=False, help='Some debug')
parser.add_argument('--debug-more', action='store_true', default=False, help='Some more debug')
parser.add_argument('--one', action='store_true', default=False, help='Stop after the first file written.')

parser.add_argument('--print-tree', action='store_true', help='Only print XML tree structure')
parser.add_argument('--tree-output', type=argparse.FileType('w'), help='Where to store XML tree structure. Use \'-\' for stdout.')

parser.add_argument('file', type=str, help='Source XML file')
parser.add_argument('output', type=str, help='Output directory')

args = parser.parse_args()

doc = parse(args.file)
indent_level = 0
visited = []
old = None

structure = nx.DiGraph()

is_syceron = False

accepted_seance_context = [
  re.compile("CompteRendu@Metadonnees@DateSeance"),
  re.compile("CompteRendu@Metadonnees@Sommaire@Sommaire1@TitreStruct@Intitule"),
  re.compile("CompteRendu@Contenu@Quantiemes@Journee"),
  #re.compile("CompteRendu@Contenu@ouverture_seance@paragraphe@ORATEURS@ORATEUR@NOM"),
  re.compile(".*@paragraphe@texte$"),
]
seance_context = None

accepted_code_style = [
  'NORMAL'
]

superscript_chars_mapping = {
  '0': u'\u2070',
  '1': u'\u00b9',
  '2': u'\u00b2',
  '3': u'\u00b3',
  '4': u'\u2074',
  '5': u'\u2075',
  '6': u'\u2076',
  '7': u'\u2077',
  '8': u'\u2078',
  '9': u'\u2079',

  '0 ': u'\u2070 ',
  '1 ': u'\u00b9 ',
  '2 ': u'\u00b2 ',
  '3 ': u'\u00b3 ',
  '4 ': u'\u2074 ',
  '5 ': u'\u2075 ',
  '6 ': u'\u2076 ',
  '7 ': u'\u2077 ',
  '8 ': u'\u2078 ',
  '9 ': u'\u2079 ',

  'o': 'uméro',
  'os': 'uméros',
  'e': 'ième',
  'er': 'ier',
  'ER': 'IER',
  're': 'ière',
  'ème': 'ième',
  'eme': 'ième',
  'ter': 'ter',

  'o ': 'uméro ',
  'os ': 'uméros ',
  'e ': 'ième ',
  'er ': 'ier ',
  'er.': 'ier.',
  'er,': 'ier,',
  ' ': '',
}

subscript_chars_mapping = {
  '0': u'\u2080',
  '1': u'\u2081',
  '2': u'\u2082',
  '3': u'\u2083',
  '4': u'\u2084',
  '5': u'\u2085',
  '6': u'\u2086',
  '7': u'\u2087',
  '8': u'\u2088',
  '9': u'\u2089',

  '0 ': u'\u2080 ',
  '1 ': u'\u2081 ',
  '2 ': u'\u2082 ',
  '3 ': u'\u2083 ',
  '4 ': u'\u2084 ',
  '5 ': u'\u2085 ',
  '6 ': u'\u2086 ',
  '7 ': u'\u2087 ',
  '8 ': u'\u2088 ',
  '9 ': u'\u2089 ',

  'e': u'\u2091',
  ' ': '',
}

if not os.path.isdir(args.output):
  print('Directory does not exists', args.output, file=sys.stderr)
  sys.exit(1)

for event, node in doc:
  if not is_syceron:
    if event == START_ELEMENT:
      is_syceron = node.tagName == "syceronBrut"
    continue

  if event == CHARACTERS:
    if type(node) == Text:
      if not node.nodeValue.isprintable():
        continue

  if event == START_ELEMENT:
    indent_level += 2
    if type(node) == Element:
      if args.print_tree and len(visited) > 0:
        structure.add_edge(visited[-1].tagName, node.tagName)

      visited.append(node)
      
      if node.tagName == "DateSeance":
        if seance_context is not None and 'texte' in seance_context:
          output_seance_name = os.path.join(args.output, seance_context['DateSeance'][0])
          if os.path.isfile(output_seance_name + '.txt'):
            output_seance_name += str(int(datetime.datetime.timestamp(datetime.datetime.utcnow())))

          output_seance_name += '.txt'
          print('output_seance_name', output_seance_name)
          with open(output_seance_name, 'w') as output_seance:
            output_seance.write('.\n'.join((' '.join(seance_context['texte'])).split('. ')))

          if args.one:
            break

        seance_context = {}

  if args.debug:
    print("DEBUG:", "/".join(visited), visited)
    print("DEBUG:", " "*indent_level, str(type(node)), ":", node.toxml())

  if type(node) == Text:
    visitedFullPath = "@".join(map(lambda x: x.tagName, visited))
    
    if args.debug_more:
        print("DEBUG:", "visitedFullPath=" + visitedFullPath, ":", node.nodeValue, )

    if any(regex.match(visitedFullPath) for regex in accepted_seance_context):
      try:
        seance_context[visited[-1:][0].tagName].append(node.nodeValue)
      except KeyError:
        seance_context[visited[-1:][0].tagName] = [ node.nodeValue ]
    else:
      ## Collasping childrens of "texte" such as "exposant", "italique", ...
      if len(visited) >= 3 and visited[-2].tagName == 'texte' and 'code_style' in visited[-3].attributes and visited[-3].attributes['code_style'].value in accepted_code_style:
        ##print("LOLILOL", visited[-2], visited[-1], seance_context[visited[-2:][0]])

        toAdd = node.nodeValue

        if visited[-1].tagName == 'indice':
          if node.nodeValue in subscript_chars_mapping:
            toAdd = subscript_chars_mapping[node.nodeValue]
          else:
            # Reset to nothing because we don't really care
            toAdd = ''
            print(visited[-1].tagName, "'{}'".format(node.nodeValue), seance_context[visited[-2:][0].tagName][-1])

        elif visited[-1].tagName == 'exposant':
          if node.nodeValue in superscript_chars_mapping:
            toAdd = superscript_chars_mapping[node.nodeValue]
          else:
            print(visited[-1].tagName, "'{}'".format(node.nodeValue), seance_context[visited[-2:][0].tagName][-1])

        elif visited[-1].tagName == 'italique':
          pass

        else:
          print('UNKNOWN', visited[-1].tagName, "'{}'".format(node.nodeValue), seance_context[visited[-2:][0].tagName][-1])

        if len(toAdd) > 0:
          try:
            seance_context[visited[-2:][0].tagName][-1] += toAdd
          except KeyError:
            print("KeyError", visited, toAdd)
            ##seance_context[visited[-2:][0].tagName][-1] = [ node.nodeValue ]

  if event == END_ELEMENT:
    indent_level -= 2
    if type(node) == Element and len(visited) > 0:
      old = visited.pop()

if args.tree_output:
  print(nx_pydot.to_pydot(structure), file=sys.stdout if args.tree_output == '-' else args.tree_output)
