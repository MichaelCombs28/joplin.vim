#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
from datetime import datetime

import vim

from . import options, variable
from .node import FolderNode, NoteNode, ResourceNode, TagNode
from .tree import TreeNode
from .variable import bufname, get_joplin, root_treenodes

props = {
    'joplin_folder': 'Identifier',
    'joplin_todo': 'Todo',
    'joplin_completed': 'Comment',
    'joplin_help_title': 'Define',
    'joplin_window_title': 'Constant',
    'joplin_help_keyword': 'Identifier',
    'joplin_help_summary': 'String',
    'joplin_help_sperate': 'String',
    'joplin_help_prefix': 'String',
    'joplin_popup_info_tag': 'Statement',
    'joplin_popup_guide': 'Comment',
    'joplin_popup_indicator': 'MenuItemIndicator',
}

for name, highlight in props.items():
    vim.Function('prop_type_add')(name, {'highlight': highlight})


def set_options():
    vim.current.buffer.options['bufhidden'] = 'hide'
    vim.current.buffer.options['buftype'] = 'nofile'
    vim.current.buffer.options['swapfile'] = False
    vim.current.buffer.options['filetype'] = 'joplin'
    vim.current.buffer.options['modifiable'] = False
    vim.current.buffer.options['readonly'] = False
    vim.current.buffer.options['buflisted'] = False
    vim.current.buffer.options['textwidth'] = 0
    vim.current.window.options['signcolumn'] = 'no'
    vim.current.window.options['winfixwidth'] = True
    vim.current.window.options['foldcolumn'] = 0
    vim.current.window.options['foldmethod'] = 'manual'
    vim.current.window.options['foldenable'] = False
    vim.current.window.options['list'] = False
    vim.current.window.options['spell'] = False
    vim.current.window.options['wrap'] = False
    vim.current.window.options['number'] = True
    vim.current.window.options['relativenumber'] = False
    vim.current.window.options['cursorline'] = True


def set_map():
    for lhs in variable.unmap:
        cmd = 'nnoremap <script><buffer>%s <nop>' % lhs
        vim.command(cmd)
    for lhs, rhs in variable.treenode_mapping.items():
        cmd = 'nnoremap <script><buffer>%s <esc>:<c-u>python3 ' \
                'pyjoplin.treenode_cmd("%s")<cr>' % (lhs, rhs)
        vim.command(cmd)
    for lhs, rhs in variable.win_mapping.items():
        cmd = 'nnoremap <script><buffer>%s <esc>:<c-u>python3 ' \
                'pyjoplin.run("%s")<cr>' % (lhs, rhs)
        vim.command(cmd)


def open_window():
    """open joplin window
    """
    bufname_ = bufname()
    winnr = vim.Function('bufwinnr')(bufname_)
    if winnr != -1:
        vim.command('%dwincmd w' % winnr)
        return
    vim.command('silent keepalt topleft vertical %d split %s' %
                (options.window_width, bufname_))
    set_options()
    set_map()
    render()
    last_line = vim.current.buffer.vars.get('saved_last_line',
                                            len(variable.window_title) + 1)
    vim.Function('cursor')(last_line, 1)


def close_window():
    bufname_ = bufname()
    winnr = vim.Function('bufwinnr')(bufname_)
    if winnr > 0:
        vim.command('%dclose' % winnr)


def toggle_window():
    if vim.Function('bufwinnr')(bufname()) > 0:
        close_window()
    else:
        open_window()


def write(note_id, **kwargs):
    note = get_joplin().get(NoteNode, note_id)
    if note is None:
        return

    note.body = '\n'.join(vim.current.buffer[:])
    get_joplin().put(note)


def saveas(**kwargs):
    if 'folder' not in kwargs:
        print('Joplin: please select a notebook')
        return
    folder = kwargs['folder']
    path = folder.split('/')
    root = TreeNode()
    root.children = root_treenodes()
    for p in path:
        match = list(
            filter(lambda node: node.node.title == p and node.is_folder(),
                   root.children))
        if len(match) == 0:
            print('Joplin: not such notebook<%s>' % folder)
            return
        root = match[0]

    if root.node is None:
        print('Joplin: not such notebook <%s>' % folder)
        return

    note = NoteNode(parent_id=root.node.id)
    body = '\n'.join(vim.current.buffer[:])
    note.title = vim.Function('expand')('%:p:t').decode()
    note.body = body
    note = get_joplin().post(note)
    if note is None:
        print('Joplin: New note failed')
        return
    note_local_setting()
    vim.current.buffer.vars['joplin_note_id'] = note.id
    vim.command('noautocmd w')


def prop_add(nr, prop_type, col_begin=1, col_end=0):
    if prop_type == '':
        return
    vim.Function('cursor')(nr, 1)
    if col_end == 0:
        col_end = vim.Function('col')('$')
    vim.Function('prop_add')(nr, col_begin, {
        'end_col': col_end,
        'type': prop_type,
    })


def render_help(nr):
    lines = variable.help_lines if has_help() else []
    for text in lines:
        vim.current.buffer.append(text, nr)
        prop_add(nr + 1, 'joplin_help_prefix', 1, 3)
        if re.match(r'^# =+$|^# -+$', text):
            prop_add(nr + 1, 'joplin_help_sperate', 3)
        elif re.match(r'^# .*~$', text):
            prop_add(nr + 1, 'joplin_help_title', 3)
        elif re.match(r'^# [^:]*:.*$', text):
            vim.Function('cursor')(nr + 1, 1)
            vim.command('noautocmd normal f:')
            col = vim.Function('col')('.')
            prop_add(nr + 1, 'joplin_help_keyword', 3, col)
            prop_add(nr + 1, 'joplin_help_summary', col)
        nr += 1
    return nr


def render_title(nr):
    for text in variable.window_title:
        vim.current.buffer.append(text, nr)
        prop_add(nr + 1, 'joplin_window_title')
        nr += 1
    return nr


def note_text(nodes, indent):
    lines = []
    for node in nodes:
        node.indent = indent
        lines.append(node)
        if node.is_open():
            sub = note_text(node.children, indent + 1)
            lines += sub
    return lines


def render_nodes(nr):
    treenodes = root_treenodes()
    lines = note_text(treenodes, 0)
    for line in lines:
        vim.current.buffer.append(
            line.text(options.icon_open, options.icon_close, options.icon_note,
                      options.icon_todo, options.icon_completed), nr)
        line.lineno = nr + 1
        prop_type = line.prop_type()
        prop_add(nr + 1, prop_type)
        nr += 1
    return nr


def render():
    vim.current.buffer.options['modifiable'] = True
    del vim.current.buffer[:]
    nr = 0
    nr = render_help(nr)
    nr = render_title(nr)
    nr = render_nodes(nr)
    # delete empty line
    del vim.current.buffer[nr]
    vim.current.buffer.options['modifiable'] = False


def edit(command, treenode):
    lazyredraw_saved = vim.options['lazyredraw']
    winview_saved = vim.Function('winsaveview')()
    dirname = vim.eval('tempname()')
    os.mkdir(dirname)
    filename = dirname + '/' + treenode.node.title + '.md'
    vim.command('silent %s %s' % (command, filename))
    vim.current.buffer.vars['joplin_note_id'] = treenode.node.id
    vim.current.buffer.vars['joplin_treenode_line'] = treenode.lineno
    treenode.fetch_note(get_joplin())
    vim.options['lazyredraw'] = True
    vim.current.buffer[:] = treenode.node.body.split('\n')
    vim.command('silent noautocmd w')
    # check joplin window
    # reopen if not exist
    winnr = vim.Function('bufwinnr')(bufname())
    if winnr < 0:
        note_bufname = vim.Function('bufname')()
        open_window()
        vim.Function('winrestview')(winview_saved)
        winnr = vim.Function('bufwinnr')(note_bufname)
        vim.command('%dwincmd w' % winnr)

    vim.command('redraw!')
    vim.options['lazyredraw'] = lazyredraw_saved
    note_local_setting()


def note_local_setting():
    vim.command(
        'autocmd BufWritePost <buffer> python3 pyjoplin.note_cmd("write")')

    # command for note
    vim.command('command! -buffer -nargs=0 JoplinNoteInfo python3 '
                'pyjoplin.note_cmd("cmd_note_info")')
    vim.command('command! -buffer -nargs=0 JoplinNoteTypeConvert python3 '
                'pyjoplin.note_cmd("cmd_note_type_convert")')
    vim.command('command! -buffer -nargs=0 JoplinNoteCompleteConvert python3 '
                'pyjoplin.note_cmd("cmd_note_complete_convert")')

    # command for tag
    vim.command(
        'command! -buffer -nargs=1 -complete=customlist,JoplinAllTagComplete '
        'JoplinTagAdd python3 '
        'pyjoplin.note_cmd("cmd_tag_add", title=<q-args>)')
    vim.command(
        'command! -buffer -nargs=1 -complete=customlist,JoplinNoteTagComplete '
        'JoplinTagDel python3 '
        'pyjoplin.note_cmd("cmd_tag_del", title=<q-args>)')

    # command for resource
    vim.command(
        'command! -buffer -nargs=1 -complete=file JoplinResourceAttach python3'
        ' pyjoplin.note_cmd("cmd_resource_attach", file=<q-args>)')

    # command for link
    vim.command(
        'command! -buffer -nargs=1 '
        '-complete=customlist,JoplinAllResourceComplete JoplinLinkResource '
        'python3 pyjoplin.note_cmd("cmd_link_resource", title=<q-args>)')
    vim.command('command! -buffer -nargs=1 '
                '-complete=custom,JoplinNoteComplete JoplinLinkNote '
                'python3 pyjoplin.note_cmd("cmd_link_note", title=<q-args>)')


def refresh_render(treenode):
    refresh(treenode)
    render()


def refresh(treenode):
    if treenode is None:
        return
    if not treenode.is_folder():
        return
    if not treenode.is_open():
        # if the current node is close
        # not need to refresh current node
        # buf if it has fetch data, sould set to dirty
        # it will fetch data when open
        treenode.dirty = treenode.fetched
        return
    treenode.fetch_folder(get_joplin(), options.pin_todo,
                          options.hide_completed, options.folder_order_by,
                          options.folder_order_desc, options.note_order_by,
                          options.note_order_desc)
    for child in treenode.children:
        refresh(child)


# ============================== run functions
def run(funcname, **kwargs):
    eval('%s(**kwargs)' % funcname)


def treenode_cmd(funcname, **kwargs):
    treenode = get_cur_line()
    if treenode is None:
        return
    eval("%s(treenode, **kwargs)" % funcname)


def note_cmd(funcname, **kwargs):
    note_id = vim.current.buffer.vars.get('joplin_note_id', b'').decode()
    if note_id == '':
        return
    eval("%s(note_id, **kwargs)" % funcname)


# ============================== complete
def note_tag_titles():
    note_id = vim.current.buffer.vars.get('joplin_note_id', b'').decode()
    if note_id == '':
        return []
    return list([tag.title for tag in get_joplin().get_note_tags(note_id)])


def all_resource_titles():
    resources = get_joplin().get_all(ResourceNode)
    titles = list([resource.title for resource in resources])
    return titles


def all_tag_titles():
    tags = get_joplin().get_all(TagNode)
    titles = list([tag.title for tag in tags])
    return titles


def note_match_text(**kwargs):
    if 'arg_lead' not in kwargs or 'var' not in kwargs:
        return
    arg_lead = kwargs['arg_lead']
    var = kwargs['var']
    vim.current.buffer.vars[var] = ''
    path = arg_lead.split(r'/')
    path = list(filter(lambda p: re.match(r'^\s*$', p) is None, path[:-1]))
    dirname = '/'.join(path)
    nodes = root_treenodes()
    for p in path:
        nodes = list(
            filter(lambda node: node.is_folder() and node.node.title == p,
                   nodes))
        if len(nodes) == 0:
            return
        nodes = nodes[0].children

    if len(nodes) == 0:
        return
    for node in nodes:
        node.fetch_folder(get_joplin(), options.pin_todo,
                          options.hide_completed, options.folder_order_by,
                          options.folder_order_desc, options.note_order_by,
                          options.note_order_desc)
    lines = list([dirname + '/' + node.node.title for node in nodes])
    lines = list(
        map(lambda line: line[1:] if line.startswith('/') else line, lines))
    text = '\n'.join(lines)
    vim.current.buffer.vars[var] = text


def folder_match_text(**kwargs):
    if 'arg_lead' not in kwargs or 'var' not in kwargs:
        return
    arg_lead = kwargs['arg_lead']
    var = kwargs['var']
    vim.current.buffer.vars[var] = ''
    path = arg_lead.split(r'/')
    path = list(filter(lambda p: re.match(r'^\s*$', p) is None, path[:-1]))
    dirname = '/'.join(path)
    nodes = root_treenodes()
    for p in path:
        nodes = list(
            filter(lambda node: node.is_folder() and node.node.title == p,
                   nodes))
        if len(nodes) == 0:
            return
        nodes = nodes[0].children

    if len(nodes) == 0:
        return
    lines = list([dirname + '/' + node.node.title for node in nodes])
    lines = list(
        map(lambda line: line[1:] if line.startswith('/') else line, lines))
    text = '\n'.join(lines)
    vim.current.buffer.vars[var] = text


def works2bvar(**kwargs):
    if 'var' not in kwargs or 'wordsfunc' not in kwargs:
        return
    var = kwargs['var']
    wordsfunc = kwargs['wordsfunc']
    titles = eval(wordsfunc + '()')
    vim.current.buffer.vars[var] = titles


# ============================== treenode cmd
def cmd_o(treenode):
    if treenode.is_folder():
        if treenode.is_open():
            treenode.close()
        else:
            treenode.open(get_joplin(), options.pin_todo,
                          options.hide_completed, options.folder_order_by,
                          options.folder_order_desc, options.note_order_by,
                          options.note_order_desc)
        saved_pos = vim.eval('getcurpos()')
        render()
        vim.Function('setpos')('.', saved_pos)
    else:
        go_to_previous_win()
        edit('edit', treenode)


def cmd_t(treenode):
    if not treenode.is_folder():
        edit('tabnew', treenode)


def cmd_i(treenode):
    if not treenode.is_folder():
        go_to_previous_win()
        edit('split', treenode)


def cmd_s(treenode):
    if not treenode.is_folder():
        go_to_previous_win()
        edit('vsplit', treenode)


def open_recusively(treenode):
    if treenode.is_folder() and not treenode.is_open():
        treenode.open(get_joplin(), options.pin_todo, options.hide_completed,
                      options.folder_order_by, options.folder_order_desc,
                      options.note_order_by, options.note_order_desc)

    for child in treenode.children:
        open_recusively(child)


def cmd_O(treenode):
    if treenode.is_folder():
        open_recusively(treenode)
        render()
        cursor(treenode)


def cmd_x(treenode):
    treenode = treenode if \
        treenode.is_folder() and treenode.is_open() else \
        treenode.parent
    while treenode is not None and not treenode.is_folder():
        treenode = treenode.parent

    if treenode is not None:
        treenode.close()
        render()
        cursor(treenode)


def close_recurisive(node):
    if not node.is_folder() or not node.is_open():
        return

    node.close()
    for child in node.children:
        close_recurisive(child)


def cmd_X(treenode):
    if not treenode.is_folder():
        return
    close_recurisive(treenode)
    render()
    cursor(treenode)


def cmd_r(treenode):
    lastnode = treenode
    if not treenode.is_folder():
        treenode = treenode.parent
    refresh_render(treenode)
    cursor(lastnode)
    print('Joplin: Refreshed!')


def cmd_R(treenode):
    lastnode = treenode
    while treenode.parent is not None:
        treenode = treenode.parent
    refresh_render(treenode)
    cursor(lastnode)
    print('Joplin: Refreshed!')


def cmd_P(treenode):
    while treenode.parent is not None:
        treenode = treenode.parent
    cursor(treenode)


def cmd_p(treenode):
    treenode = treenode.parent if treenode.parent is not None else treenode
    cursor(treenode)


def cmd_K(treenode):
    nodes = treenode.parent.children if \
        treenode.parent is not None else \
        root_treenodes()
    if len(nodes) > 0:
        cursor(nodes[0])


def cmd_J(treenode):
    nodes = treenode.parent.children if \
        treenode.parent is not None else \
        root_treenodes()
    if len(nodes) > 0:
        cursor(nodes[-1])


def cmd_ctrl_j(treenode):
    nodes = treenode.parent.children if \
        treenode.parent is not None else \
        root_treenodes()
    i = treenode.child_index_of_parent + 1
    if i < len(nodes):
        cursor(nodes[i])


def cmd_ctrl_k(treenode):
    nodes = treenode.parent.children if \
        treenode.parent is not None else \
        root_treenodes()
    i = treenode.child_index_of_parent - 1
    if i >= 0:
        cursor(nodes[i])


def cmd_q():
    close_window()


def cmd_question_mark():
    joplin_help = has_help()
    vim.current.buffer.vars['joplin_help'] = not joplin_help
    render()
    vim.Function('cursor')(1, 1)


# ============================== menu cmds
def menu_callback(treenode, **kwargs):
    if 'result' not in kwargs:
        return
    result = kwargs['result']
    if result > len(menu_items) or result <= 0:
        return
    menu_items[result - 1].callback(treenode)


def menu_add(treenode):
    print('add', treenode.node.title)


def menu_move(treenode):
    print('move', treenode.node.title)


def menu_delete(treenode):
    prompt = ''
    if treenode.is_folder():
        prompt = 'Delete notebook <%s>?*All notes and sub-notebooks within ' \
            'this notebook will also be deleted* (y/N): ' % treenode.node.title
    else:
        prompt = 'Delete note <%s>? (y/N)' % treenode.node.title

    cls = FolderNode if treenode.is_folder() else NoteNode
    # select = vim.Function('input')(prompt)
    vim.command('echo "Joplin: %s"' % prompt)
    select = 0
    # 89 == Y, 121 == y, 78 == N, 110 == n
    while select not in [89, 121, 78, 110]:
        select = vim.Function('getchar')()
        if select in [89, 121]:
            get_joplin().delete(cls, treenode.node.id)
            vim.command('echo "Joplin: <%s> deleted"' % treenode.node.title)
            line = vim.Function('line')('.')
            if treenode.parent is None:
                variable.del_rootnode(treenode.node.id)
                render()
            else:
                treenode.parent.children = variable.delete_node_in_list(
                    treenode.parent.children, treenode.node.id)
                render()

            vim.Function('cursor')(line, 1)
        elif select in [78, 110]:
            vim.command('echo "Joplin: delete aborted"')


def menu_copy(treenode):
    print('copy', treenode.node.title)


class MenuItem(object):
    def __init__(self, text, indicator_index, callback):
        self.text = text
        self.indicator_index = indicator_index
        self.callback = callback


menu_items = [
    MenuItem('add a childnode', 0, menu_add),
    MenuItem('move the current code', 0, menu_move),
    MenuItem('delete the current node', 0, menu_delete),
    MenuItem('copy the current node', 0, menu_copy)
]


def cmd_m():
    text = list([{
        'text':
        item.text,
        'props': [{
            'type': 'joplin_popup_indicator',
            'col': item.indicator_index + 1,
            'length': 1
        }],
    } for item in menu_items])

    vim.Function('popup_menu')(text, {
        'title': 'Joplin menu',
        'filter': 'joplin#popup#menu_filter',
        'callback': 'joplin#popup#menu_callback',
    })
    vim.command('echo "%s"' % variable.menu_popup_guide)


# ============================== note cmds
class NoteInfo(object):
    def __init__(self, tag, data):
        self.tag = tag
        self.data = data

    def text(self, tag_len):
        padding = (tag_len - len(self.tag)) * ' '
        return self.tag + padding + ' : ' + self.data


def cmd_note_info(note_id, **kwargs):
    note = get_joplin().get(NoteNode, note_id, ['body'])
    if note is None:
        print('Joplin: not such node <%s>' % note_id)
        return
    title = ' Information for %s ' % note.title
    path = get_joplin().node_path(note)
    tags = list([tag.title for tag in get_joplin().get_note_tags(note_id)])
    infos = []
    infos.append(NoteInfo('Id', note_id))
    infos.append(NoteInfo('Path', path))
    infos.append(NoteInfo('Markdown link', note.markdown_link()))
    infos.append(NoteInfo('Update time', strftime(note.updated_time)))
    infos.append(NoteInfo('Create time', strftime(note.created_time)))
    infos.append(NoteInfo('Tags', str(tags)))
    max_tag_len = max([len(info.tag) for info in infos])

    props = [{
        'type': 'joplin_popup_info_tag',
        'col': 1,
        'length': max_tag_len,
    }]
    text = list([{
        'text': info.text(max_tag_len),
        'props': props
    } for info in infos])
    text.append({
        'text':
        variable.info_popup_guide,
        'props': [{
            'type': 'joplin_popup_guide',
            'col': 1,
            'length': len(variable.info_popup_guide),
        }]
    })

    vim.Function('popup_dialog')(text, {
        'title': title,
        'filter': 'joplin#popup#info_filter',
        'highlight': 'InfoMenu',
        'mapping': 0,
    })


def cmd_tag_add(note_id, **kwargs):
    if 'title' not in kwargs:
        return
    title = kwargs['title']
    # the note has the tag
    had_titles = list(
        [tag.title for tag in get_joplin().get_note_tags(note_id)])
    if title in had_titles:
        return
    tags = get_joplin().get_all(TagNode)
    # tag exists
    tags = list(filter(lambda tag: tag.title == title, tags))
    if len(tags) > 0:
        find = tags[0]
    else:
        find = get_joplin().post(TagNode(title=title))
    if find is not None:
        get_joplin().post_tag_note(find.id, note_id)


def cmd_tag_del(note_id, **kwargs):
    if 'title' not in kwargs:
        return
    title = kwargs['title']
    tags = list(
        filter(lambda tag: tag.title == title,
               get_joplin().get_note_tags(note_id)))
    if len(tags) > 0:
        get_joplin().delete_tag_note(tags[0].id, note_id)


def cmd_note_type_convert(note_id, **kwargs):
    note = get_joplin().get(NoteNode, note_id)
    note.is_todo ^= 1
    note.todo_completed = 0
    get_joplin().put(note)
    line = vim.current.buffer.vars.get('joplin_treenode_line', -1)
    if line != -1:
        refresh_treenode_line(line)


def cmd_note_complete_convert(note_id, **kwargs):
    note = get_joplin().get(NoteNode, note_id)
    if not note.is_todo:
        print('Joplin: not a todo')
        return
    note.todo_completed ^= 1
    get_joplin().put(note)
    line = vim.current.buffer.vars.get('joplin_treenode_line', -1)
    if line != -1:
        refresh_treenode_line(line)


def cmd_resource_attach(note_id, **kwargs):
    if 'file' not in kwargs:
        return
    filepath = kwargs['file']
    title = os.path.basename(filepath)
    resource = ResourceNode(title=title)
    resource = get_joplin().post_resource(filepath, resource)
    if resource.id == '':
        print('Joplin: attach resource failed')
        return
    insert_resource(resource)


def cmd_link_resource(note_id, **kwargs):
    if 'title' not in kwargs:
        print('Joplin: please select a resource')
        return
    title = kwargs['title']
    resources = get_joplin().get_all(ResourceNode)
    matched = list(filter(lambda resource: resource.title == title, resources))
    if len(matched) == 0:
        print('Joplin: not such resource <%s>' % title)
        return
    insert_resource(matched[0])


def cmd_link_note(note_id, **kwargs):
    if 'title' not in kwargs:
        print('Joplin: please select a note')
        return
    title = kwargs['title']
    path = title.split('/')
    root = TreeNode()
    root.children = root_treenodes()
    for p in path:
        match = list(filter(lambda node: node.node.title == p, root.children))
        if len(match) == 0:
            print('Joplin: not such note <%s>' % title)
            return
        root = match[0]
    if root.node is None:
        print('Joplin: not such note <%s>' % title)
        return
    vim.command('normal! a' + root.node.markdown_link())


# ============================== util for cmd function
def insert_resource(resource):
    text = resource.markdown_link()
    vim.command('normal! a' + text)


def find_treenode(nodes, lineno):
    nodes = list(filter(lambda node: node.lineno > 0, nodes))
    i = 0
    j = len(nodes) - 1

    if i > j:
        return None
    if nodes[j].lineno < lineno:
        return find_treenode(nodes[j].children,
                             lineno) if nodes[j].is_folder() else None
    while i <= j:
        mid = int((i + j) / 2)
        if nodes[mid].lineno == lineno:
            return nodes[mid]
        elif nodes[mid].lineno < lineno:
            i = mid + 1
        elif nodes[mid].lineno > lineno:
            j = mid - 1

    mid = i if nodes[i].lineno < lineno else i - 1
    return find_treenode(nodes[mid].children,
                         lineno) if nodes[mid].is_folder() else None


def base_line():
    return len(variable.window_title) + (len(variable.help_lines)
                                         if has_help() else 0)


def get_cur_line():
    lineno = int(vim.eval('line(".")'))
    if lineno <= base_line():
        return None
    return find_treenode(variable.root_treenodes(), lineno)


def cursor(treenode):
    if treenode.lineno > 0:
        vim.Function('cursor')(treenode.lineno, 1)


def refresh_treenode_line(line):
    winnr = vim.Function('bufwinnr')(bufname())
    if winnr <= 0:
        return
    winnr_saved = vim.Function('winnr')()
    lazyredraw_saved = vim.options['lazyredraw']
    vim.options['lazyredraw'] = True
    vim.command('%dwincmd w' % winnr)
    treenode = find_treenode(root_treenodes(), line)
    if treenode is not None and not treenode.is_folder():
        treenode = treenode.parent
    refresh_render(treenode)
    vim.command('%dwincmd w' % winnr_saved)
    vim.command('redraw!')
    vim.options['lazyredraw'] = lazyredraw_saved


def go_to_previous_win():
    saved_prev_winnr = vim.current.buffer.vars.get('saved_prev_winnr', -1)
    if saved_prev_winnr > 0:
        vim.command('%dwincmd w' % saved_prev_winnr)
    else:
        vim.command('wincmd w')


def has_help():
    return vim.current.buffer.vars.get('joplin_help', False)


def strftime(timestamp):
    return datetime.fromtimestamp(timestamp /
                                  1000.0).strftime('%Y-%m-%d %H:%M:%S')
