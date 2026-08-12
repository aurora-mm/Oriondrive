from __future__ import annotations
import threading
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional
import objc
from AppKit import NSApplication, NSApplicationActivationPolicyRegular, NSBezelBorder, NSBox, NSButton, NSButtonCell, NSButtonTypeSwitch, NSColor, NSControlSizeSmall, NSFont, NSGridView, NSImage, NSLayoutAttributeLeading, NSLayoutConstraint, NSLineBreakByWordWrapping, NSMenu, NSMenuItem, NSNoTabsNoBorder, NSOpenPanel, NSOutlineView, NSPopUpButton, NSPopUpButtonCell, NSProgressIndicator, NSProgressIndicatorSpinningStyle, NSSavePanel, NSScrollView, NSSplitViewController, NSSplitViewItem, NSStackView, NSStackViewGravityLeading, NSTableColumn, NSTableView, NSTableViewSelectionHighlightStyleSourceList, NSTabView, NSTabViewItem, NSTextField, NSTextFieldCell, NSToolbar, NSToolbarItem, NSUserInterfaceLayoutOrientationVertical, NSView, NSViewController, NSWindow, NSWindowStyleMaskClosable, NSWindowStyleMaskFullSizeContentView, NSWindowStyleMaskMiniaturizable, NSWindowStyleMaskResizable, NSWindowStyleMaskTitled
from Foundation import NSMakeRect, NSObject, NSSize
from PyObjCTools import AppHelper
from ..config import DEFAULT_MIN_DURATION_SECONDS
from ..generation import default_variations_dir, generate_project, write_seed_variations
from ..grooves import AUTO_GROOVE, VALID_GROOVE_NAMES
from ..harmonic_seeds import AUTO_SEED, VALID_SEED_NAMES
from ..midi_writer import write_midi
from ..ori_format import load_ori, save_ori
from ..reports import default_candidate_output_dir, default_fitness_report_path, write_fitness_report
from . import state as project_state
WINDOW_SIZE = NSSize(1220, 820)
MIN_WINDOW_SIZE = NSSize(1000, 680)
SIDEBAR_WIDTH = 232.0
TAB_KEYS = ('song', 'harmony', 'variation', 'advanced', 'variations')
TAB_TITLES = {'song': 'Song Structure', 'harmony': 'Harmonic Seeds', 'variation': 'Groove & Variation', 'advanced': 'Advanced', 'variations': 'Generated Songs'}
SECTION_COLUMNS = (('name', 'Section', 190, None), ('length_bars', 'Bars', 52, None), ('energy', 'Energy', 62, None), ('lead_role', 'Lead', 118, 'lead'), ('riff_role', 'Riff', 118, 'riff'), ('bass_role', 'Bass', 104, 'bass'), ('drum_role', 'Drums', 104, 'drum'), ('pad_role', 'Pad', 96, 'pad'))
VARIATION_COLUMNS = (('rank', '#', 30), ('label', 'Harmonic seed', 150), ('groove', 'Groove', 130), ('mode', 'Mode', 100), ('tempo', 'BPM', 50), ('progression', 'Chord field', 210), ('score', 'Score', 60))
NSLayoutAttributeCenterY_CONSTANT = 10
NSGridCellPlacementLeading = 2
NSGridCellPlacementTrailing = 3

def _label(text: str, *, bold: bool=False, secondary: bool=False, size: float=0.0) -> NSTextField:
    field = NSTextField.labelWithString_(text)
    point = size or NSFont.systemFontSize()
    field.setFont_(NSFont.boldSystemFontOfSize_(point) if bold else NSFont.systemFontOfSize_(point))
    if secondary:
        field.setTextColor_(NSColor.secondaryLabelColor())
    field.setLineBreakMode_(NSLineBreakByWordWrapping)
    return field

def _text_field(value: str, width: float=120.0) -> NSTextField:
    field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, width, 22))
    field.setStringValue_(value)
    field.setBezeled_(True)
    field.setDrawsBackground_(True)
    field.setEditable_(True)
    field.setTranslatesAutoresizingMaskIntoConstraints_(False)
    field.widthAnchor().constraintEqualToConstant_(width).setActive_(True)
    return field

def _popup(options, value: str, width: float=170.0) -> NSPopUpButton:
    button = NSPopUpButton.alloc().initWithFrame_pullsDown_(NSMakeRect(0, 0, width, 24), False)
    titles = [option if option != '' else '—' for option in options]
    button.addItemsWithTitles_(titles)
    display = value if value != '' else '—'
    if display in titles:
        button.selectItemWithTitle_(display)
    button.setTranslatesAutoresizingMaskIntoConstraints_(False)
    button.widthAnchor().constraintEqualToConstant_(width).setActive_(True)
    return button

def _checkbox(title: str, value: bool, target, action) -> NSButton:
    button = NSButton.checkboxWithTitle_target_action_(title, target, action)
    button.setState_(1 if value else 0)
    return button

def _push_button(title: str, target, action) -> NSButton:
    button = NSButton.buttonWithTitle_target_action_(title, target, action)
    return button

def _scrolling_table(columns, target, delegate, height: float=240.0, horizontal: bool=False) -> tuple:
    table = NSTableView.alloc().initWithFrame_(NSMakeRect(0, 0, 640, height))
    table.setUsesAlternatingRowBackgroundColors_(True)
    table.setAllowsColumnReordering_(False)
    table.setRowHeight_(22.0)
    table.setIntercellSpacing_(NSSize(3.0, 2.0))
    table.setColumnAutoresizingStyle_(0)
    for column in columns:
        table.addTableColumn_(column)
    table.setDataSource_(delegate)
    table.setDelegate_(delegate)
    table.setTarget_(target)
    scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, 640, height))
    scroll.setDocumentView_(table)
    scroll.setHasVerticalScroller_(True)
    scroll.setHasHorizontalScroller_(horizontal)
    scroll.setAutohidesScrollers_(True)
    scroll.setBorderType_(NSBezelBorder)
    scroll.setTranslatesAutoresizingMaskIntoConstraints_(False)
    scroll.heightAnchor().constraintEqualToConstant_(height).setActive_(True)
    if not horizontal:
        table.setAutoresizingMask_(2)
        scroll.setAutoresizesSubviews_(True)
    return (table, scroll)

def _text_column(identifier: str, title: str, width: float, editable: bool=True) -> NSTableColumn:
    column = NSTableColumn.alloc().initWithIdentifier_(identifier)
    column.headerCell().setStringValue_(title)
    column.setWidth_(width)
    column.setMinWidth_(max(32.0, width * 0.6))
    cell = NSTextFieldCell.alloc().initTextCell_('')
    cell.setEditable_(editable)
    cell.setFont_(NSFont.systemFontOfSize_(NSFont.smallSystemFontSize()))
    column.setDataCell_(cell)
    column.setEditable_(editable)
    return column

def _popup_column(identifier: str, title: str, width: float, options) -> NSTableColumn:
    column = NSTableColumn.alloc().initWithIdentifier_(identifier)
    column.headerCell().setStringValue_(title)
    column.setWidth_(width)
    column.setMinWidth_(max(60.0, width * 0.6))
    cell = NSPopUpButtonCell.alloc().initTextCell_pullsDown_('', False)
    cell.addItemsWithTitles_(list(options))
    cell.setBordered_(False)
    cell.setControlSize_(NSControlSizeSmall)
    cell.setFont_(NSFont.systemFontOfSize_(NSFont.smallSystemFontSize()))
    column.setDataCell_(cell)
    column.setEditable_(True)
    return column

def _checkbox_column(identifier: str, title: str, width: float) -> NSTableColumn:
    column = NSTableColumn.alloc().initWithIdentifier_(identifier)
    column.headerCell().setStringValue_(title)
    column.setWidth_(width)
    column.setMinWidth_(width)
    cell = NSButtonCell.alloc().init()
    cell.setButtonType_(NSButtonTypeSwitch)
    cell.setTitle_('')
    column.setDataCell_(cell)
    column.setEditable_(True)
    column.setMaxWidth_(width)
    column.setResizingMask_(0)
    return column

def _vertical_stack(views, spacing: float=12.0, fill: bool=True) -> NSStackView:
    stack = NSStackView.alloc().init()
    stack.setOrientation_(NSUserInterfaceLayoutOrientationVertical)
    stack.setSpacing_(spacing)
    stack.setTranslatesAutoresizingMaskIntoConstraints_(False)
    stack.setAlignment_(NSLayoutAttributeLeading)
    for view in views:
        view.setTranslatesAutoresizingMaskIntoConstraints_(False)
        stack.addView_inGravity_(view, NSStackViewGravityLeading)
    if fill:
        NSLayoutConstraint.activateConstraints_([constraint for view in views for constraint in (view.leadingAnchor().constraintEqualToAnchor_(stack.leadingAnchor()), view.trailingAnchor().constraintEqualToAnchor_(stack.trailingAnchor()))])
    return stack

def _row(views, spacing: float=16.0) -> NSStackView:
    stack = NSStackView.stackViewWithViews_(list(views))
    stack.setSpacing_(spacing)
    stack.setAlignment_(NSLayoutAttributeCenterY_CONSTANT)
    stack.setTranslatesAutoresizingMaskIntoConstraints_(False)
    return stack

def _pin(child: NSView, parent: NSView, inset: float=0.0) -> None:
    child.setTranslatesAutoresizingMaskIntoConstraints_(False)
    parent.addSubview_(child)
    NSLayoutConstraint.activateConstraints_([child.leadingAnchor().constraintEqualToAnchor_constant_(parent.leadingAnchor(), inset), child.trailingAnchor().constraintEqualToAnchor_constant_(parent.trailingAnchor(), -inset), child.topAnchor().constraintEqualToAnchor_constant_(parent.topAnchor(), inset), child.bottomAnchor().constraintEqualToAnchor_constant_(parent.bottomAnchor(), -inset)])

def _grid(rows) -> NSGridView:
    grid = NSGridView.gridViewWithViews_(rows)
    grid.setRowSpacing_(10.0)
    grid.setColumnSpacing_(14.0)
    for index in range(grid.numberOfColumns()):
        grid.columnAtIndex_(index).setXPlacement_(NSGridCellPlacementTrailing if index % 2 == 0 else NSGridCellPlacementLeading)
    grid.setTranslatesAutoresizingMaskIntoConstraints_(False)
    return grid

def _card(title: str, subtitle: str, body: NSView) -> NSView:
    box = NSBox.alloc().initWithFrame_(NSMakeRect(0, 0, 640, 200))
    box.setTitle_(title)
    box.setTitleFont_(NSFont.boldSystemFontOfSize_(NSFont.systemFontSize()))
    box.setContentViewMargins_(NSSize(14, 10))
    box.setTranslatesAutoresizingMaskIntoConstraints_(False)
    content = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 620, 180))
    body.setTranslatesAutoresizingMaskIntoConstraints_(False)
    content.addSubview_(body)
    constraints = [body.leadingAnchor().constraintEqualToAnchor_(content.leadingAnchor()), body.bottomAnchor().constraintEqualToAnchor_(content.bottomAnchor())]
    if subtitle:
        caption = _label(subtitle, secondary=True, size=NSFont.smallSystemFontSize())
        caption.setTranslatesAutoresizingMaskIntoConstraints_(False)
        caption.setPreferredMaxLayoutWidth_(760.0)
        content.addSubview_(caption)
        constraints += [caption.leadingAnchor().constraintEqualToAnchor_(content.leadingAnchor()), caption.trailingAnchor().constraintEqualToAnchor_(content.trailingAnchor()), caption.topAnchor().constraintEqualToAnchor_(content.topAnchor()), body.topAnchor().constraintEqualToAnchor_constant_(caption.bottomAnchor(), 10.0)]
    else:
        constraints.append(body.topAnchor().constraintEqualToAnchor_(content.topAnchor()))
    if isinstance(body, (NSScrollView, NSStackView)):
        constraints.append(body.trailingAnchor().constraintEqualToAnchor_(content.trailingAnchor()))
    else:
        constraints.append(body.trailingAnchor().constraintLessThanOrEqualToAnchor_(content.trailingAnchor()))
    NSLayoutConstraint.activateConstraints_(constraints)
    box.setContentView_(content)
    return box

def _scrolling_form(stack: NSStackView) -> NSScrollView:
    scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, 800, 600))
    scroll.setHasVerticalScroller_(True)
    scroll.setDrawsBackground_(False)
    scroll.setBorderType_(0)
    container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 800, 600))
    stack.setTranslatesAutoresizingMaskIntoConstraints_(False)
    container.addSubview_(stack)
    NSLayoutConstraint.activateConstraints_([stack.leadingAnchor().constraintEqualToAnchor_constant_(container.leadingAnchor(), 22.0), stack.trailingAnchor().constraintEqualToAnchor_constant_(container.trailingAnchor(), -22.0), stack.topAnchor().constraintEqualToAnchor_constant_(container.topAnchor(), 20.0), stack.bottomAnchor().constraintEqualToAnchor_constant_(container.bottomAnchor(), -20.0)])
    scroll.setDocumentView_(container)
    container.setTranslatesAutoresizingMaskIntoConstraints_(False)
    container.widthAnchor().constraintEqualToAnchor_(scroll.widthAnchor()).setActive_(True)
    return scroll

class SidebarNode:

    def __init__(self, title: str, kind: str, key: str='', children=None):
        self.title = title
        self.kind = kind
        self.key = key
        self.children: List['SidebarNode'] = list(children or [])

class OriondriveController(NSObject):

    def init(self):
        self = objc.super(OriondriveController, self).init()
        if self is None:
            return None
        self._sections: List[Dict[str, Any]] = []
        self._controls: Dict[str, Any] = {}
        self._seed_pool: List[str] = list(VALID_SEED_NAMES)
        self._seed_rows: List[Dict[str, Any]] = []
        self._groove_pool: List[str] = list(VALID_GROOVE_NAMES)
        self._table_widths: Dict[str, List[float]] = {}
        self._groove_rows: List[Dict[str, Any]] = []
        self._variations: List[Any] = []
        self._selection = None
        self._project_path: Optional[Path] = None
        self._busy = False
        self._build_sidebar_model()
        return self

    @objc.python_method
    def _build_sidebar_model(self) -> None:
        self._sidebar_roots = [SidebarNode('Project', 'group', children=[SidebarNode(TAB_TITLES[key], 'tab', key) for key in TAB_KEYS]), SidebarNode('Presets', 'group', children=[SidebarNode(project_state.GENRE_LABELS[key], 'preset', key) for key in project_state.GENRE_OPTIONS])]

    @objc.python_method
    def build(self) -> None:
        self._window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(NSMakeRect(0, 0, WINDOW_SIZE.width, WINDOW_SIZE.height), NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable | NSWindowStyleMaskFullSizeContentView, 2, False)
        self._window.setTitle_('Oriondrive')
        self._window.setSubtitle_('Deterministic MIDI composer by LR Friberg')
        self._window.setMinSize_(MIN_WINDOW_SIZE)
        self._window.setReleasedWhenClosed_(False)
        split = NSSplitViewController.alloc().init()
        split.addSplitViewItem_(self._make_sidebar_item())
        split.addSplitViewItem_(NSSplitViewItem.splitViewItemWithViewController_(self._make_detail_controller()))
        self._window.setContentViewController_(split)
        self._window.setContentSize_(WINDOW_SIZE)
        self._install_toolbar()
        self._window.center()
        self.load_preset('classic_trance')
        self._select_tab('song')
        self._window.makeKeyAndOrderFront_(None)
        self._size_tables()

    @objc.python_method
    def _make_sidebar_item(self) -> NSSplitViewItem:
        controller = NSViewController.alloc().init()
        root = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, SIDEBAR_WIDTH, 600))
        outline = NSOutlineView.alloc().initWithFrame_(NSMakeRect(0, 0, SIDEBAR_WIDTH, 600))
        column = NSTableColumn.alloc().initWithIdentifier_('name')
        column.setWidth_(SIDEBAR_WIDTH - 24)
        column.setEditable_(False)
        outline.addTableColumn_(column)
        outline.setOutlineTableColumn_(column)
        outline.setHeaderView_(None)
        outline.setFloatsGroupRows_(False)
        outline.setRowSizeStyle_(1)
        outline.setSelectionHighlightStyle_(NSTableViewSelectionHighlightStyleSourceList)
        outline.setIndentationPerLevel_(12.0)
        outline.setAllowsColumnSelection_(False)
        outline.setDataSource_(self)
        outline.setDelegate_(self)
        outline.setBackgroundColor_(NSColor.clearColor())
        scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, SIDEBAR_WIDTH, 600))
        scroll.setDocumentView_(outline)
        scroll.setHasVerticalScroller_(True)
        scroll.setDrawsBackground_(False)
        scroll.setBorderType_(0)
        _pin(scroll, root)
        controller.setView_(root)
        self._outline = outline
        item = NSSplitViewItem.sidebarWithViewController_(controller)
        item.setMinimumThickness_(200.0)
        item.setMaximumThickness_(300.0)
        try:
            item.setAllowsFullHeightLayout_(True)
        except AttributeError:
            pass
        return item

    @objc.python_method
    def _make_detail_controller(self) -> NSViewController:
        controller = NSViewController.alloc().init()
        root = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 900, 700))
        self._tabs = NSTabView.alloc().initWithFrame_(NSMakeRect(0, 0, 900, 640))
        self._tabs.setTabViewType_(NSNoTabsNoBorder)
        self._tabs.setTranslatesAutoresizingMaskIntoConstraints_(False)
        for key in TAB_KEYS:
            item = NSTabViewItem.alloc().initWithIdentifier_(key)
            item.setLabel_(TAB_TITLES[key])
            item.setView_(getattr(self, f'_make_{key}_tab')())
            self._tabs.addTabViewItem_(item)
        status_bar = self._make_status_bar()
        root.addSubview_(self._tabs)
        root.addSubview_(status_bar)
        NSLayoutConstraint.activateConstraints_([self._tabs.leadingAnchor().constraintEqualToAnchor_(root.leadingAnchor()), self._tabs.trailingAnchor().constraintEqualToAnchor_(root.trailingAnchor()), self._tabs.topAnchor().constraintEqualToAnchor_(root.topAnchor()), self._tabs.bottomAnchor().constraintEqualToAnchor_(status_bar.topAnchor()), status_bar.leadingAnchor().constraintEqualToAnchor_(root.leadingAnchor()), status_bar.trailingAnchor().constraintEqualToAnchor_(root.trailingAnchor()), status_bar.bottomAnchor().constraintEqualToAnchor_(root.bottomAnchor()), status_bar.heightAnchor().constraintEqualToConstant_(38.0)])
        controller.setView_(root)
        return controller

    @objc.python_method
    def _make_status_bar(self) -> NSView:
        bar = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 900, 38))
        bar.setTranslatesAutoresizingMaskIntoConstraints_(False)
        self._spinner = NSProgressIndicator.alloc().initWithFrame_(NSMakeRect(0, 0, 16, 16))
        self._spinner.setStyle_(NSProgressIndicatorSpinningStyle)
        self._spinner.setControlSize_(NSControlSizeSmall)
        self._spinner.setDisplayedWhenStopped_(False)
        self._spinner.setTranslatesAutoresizingMaskIntoConstraints_(False)
        self._status = _label('Ready.', secondary=True, size=NSFont.smallSystemFontSize())
        self._status.setSelectable_(True)
        self._status.setTranslatesAutoresizingMaskIntoConstraints_(False)
        separator = NSBox.alloc().initWithFrame_(NSMakeRect(0, 0, 900, 1))
        separator.setBoxType_(2)
        separator.setTranslatesAutoresizingMaskIntoConstraints_(False)
        bar.addSubview_(separator)
        bar.addSubview_(self._spinner)
        bar.addSubview_(self._status)
        NSLayoutConstraint.activateConstraints_([separator.leadingAnchor().constraintEqualToAnchor_(bar.leadingAnchor()), separator.trailingAnchor().constraintEqualToAnchor_(bar.trailingAnchor()), separator.topAnchor().constraintEqualToAnchor_(bar.topAnchor()), self._spinner.leadingAnchor().constraintEqualToAnchor_constant_(bar.leadingAnchor(), 20.0), self._spinner.centerYAnchor().constraintEqualToAnchor_(bar.centerYAnchor()), self._spinner.widthAnchor().constraintEqualToConstant_(16.0), self._status.leadingAnchor().constraintEqualToAnchor_constant_(self._spinner.trailingAnchor(), 8.0), self._status.trailingAnchor().constraintEqualToAnchor_constant_(bar.trailingAnchor(), -20.0), self._status.centerYAnchor().constraintEqualToAnchor_(bar.centerYAnchor())])
        return bar

    @objc.python_method
    def _make_song_tab(self) -> NSView:
        self._controls['title'] = _text_field('Classic Trance', 240)
        self._controls['genre'] = _popup([project_state.GENRE_LABELS[value] for value in project_state.GENRE_OPTIONS], project_state.GENRE_LABELS['classic_trance'], 180)
        self._controls['genre'].setTarget_(self)
        self._controls['genre'].setAction_('genreChanged:')
        self._controls['bpm'] = _text_field('138', 80)
        self._controls['key'] = _popup(project_state.KEY_OPTIONS, 'C', 80)
        self._controls['scale'] = _popup(project_state.SCALE_OPTIONS, 'dorian', 160)
        self._controls['generation_length_seconds'] = _text_field('420', 100)
        self._controls['seed'] = _text_field('42', 100)
        self._controls['candidates'] = _text_field('20', 80)
        self._controls['generations'] = _text_field('30', 80)
        identity = _grid([[_label('Title', bold=True), self._controls['title'], _label('Genre', bold=True), self._controls['genre']], [_label('Key', bold=True), self._controls['key'], _label('Scale', bold=True), self._controls['scale']], [_label('Tempo (BPM)', bold=True), self._controls['bpm'], _label('Target length (s)', bold=True), self._controls['generation_length_seconds']]])
        search = _grid([[_label('Random seed', bold=True), self._controls['seed'], _label('Candidates', bold=True), self._controls['candidates']], [_label('Generations', bold=True), self._controls['generations'], _label(''), _label('')]])
        for key, title in (('enable_pads', 'Pads'), ('enable_riffs', 'Riffs'), ('enable_bass', 'Bass'), ('enable_drums', 'Drums')):
            self._controls[key] = _checkbox(title, True, self, 'noop:')
        self._controls['save_report'] = _checkbox('Save fitness report', False, self, 'noop:')
        self._controls['save_candidates'] = _checkbox('Save every candidate', False, self, 'noop:')
        layers = _vertical_stack([_row([self._controls[key] for key in ('enable_pads', 'enable_riffs', 'enable_bass', 'enable_drums')]), _row([self._controls['save_report'], self._controls['save_candidates']])], spacing=8.0, fill=False)
        columns = []
        for key, title, width, role_group in SECTION_COLUMNS:
            if role_group is None:
                columns.append(_text_column(key, title, width))
            else:
                columns.append(_popup_column(key, title, width, project_state.ROLE_OPTIONS[role_group]))
        self._section_table, section_scroll = _scrolling_table(columns, self, self, height=260.0, horizontal=True)
        self._section_table.setIdentifier_('sections')
        buttons = _row([_push_button('Add', self, 'addSection:'), _push_button('Delete', self, 'deleteSection:'), _push_button('Move Up', self, 'moveSectionUp:'), _push_button('Move Down', self, 'moveSectionDown:')], spacing=8.0)
        stack = _vertical_stack([_card('Project', 'Identity, key and tempo. Section bars and BPM decide the rendered duration.', identity), _card('Form', '', self._form_detail_body()), _card('Search', 'Seed, population size and how many generations of selection to run.', search), _card('Layers', 'Which layers are rendered, and what extra diagnostics to keep.', layers), _card('Structure', "Every section's length, energy and per-layer role. Lengths must be multiples of 8 bars.", _vertical_stack([buttons, section_scroll], spacing=10.0))], spacing=18.0)
        return _scrolling_form(stack)

    @objc.python_method
    def _form_detail_body(self) -> NSView:
        self._form_detail = _label(project_state.GENRE_DESCRIPTIONS['classic_trance'], secondary=True, size=NSFont.smallSystemFontSize())
        self._form_detail.setPreferredMaxLayoutWidth_(720.0)
        return _vertical_stack([self._form_detail], spacing=0.0)

    @objc.python_method
    def _update_form_detail(self) -> None:
        if not hasattr(self, '_form_detail'):
            return
        genre = self._control_value(self._controls['genre'], 'genre')
        self._form_detail.setStringValue_(project_state.GENRE_DESCRIPTIONS.get(genre, ''))

    @objc.python_method
    def _detail_label(self) -> NSTextField:
        field = _label('', secondary=True, size=NSFont.smallSystemFontSize())
        field.setSelectable_(True)
        field.setPreferredMaxLayoutWidth_(700.0)
        field.setTranslatesAutoresizingMaskIntoConstraints_(False)
        return field

    @objc.python_method
    def _make_harmony_tab(self) -> NSView:
        for spec in project_state.HARMONY_FIELDS:
            self._controls[spec.key] = self._control_for_spec(spec)
        self._controls['harmonic_seed'].setTarget_(self)
        self._controls['harmonic_seed'].setAction_('seedChoiceChanged:')
        choice_grid = _grid([[_label('Harmonic seed', bold=True), self._controls['harmonic_seed']], [_label('Seed drift rate', bold=True), self._controls['seed_mutation_rate']], [_label('Cross-seed crossover', bold=True), self._controls['cross_seed_crossover_rate']], [_label(''), self._controls['follow_seed_mode']], [_label(''), self._controls['protect_species']]])
        self._seed_detail = self._detail_label()
        selection_body = _vertical_stack([choice_grid, self._seed_detail], spacing=14.0)
        pool_columns = [_checkbox_column('included', '', 24), _text_column('label', 'Seed', 150, editable=False), _text_column('mode', 'Mode', 100, editable=False), _text_column('progression', 'Chord field', 250, editable=False), _text_column('cadence', 'Cadence', 110, editable=False)]
        self._seed_table, seed_scroll = _scrolling_table(pool_columns, self, self, height=250.0)
        self._seed_table.setIdentifier_('seeds')
        voicing = _grid([[_label('Bars per chord', bold=True), self._controls['harmonic_rhythm_bars'], _label('Pedal strength', bold=True), self._controls['pedal_strength']], [_label('Voicing openness', bold=True), self._controls['voicing_openness'], _label('Suspension', bold=True), self._controls['suspension_amount']], [_label('Pad density', bold=True), self._controls['pad_density'], _label('Air layer', bold=True), self._controls['pad_air_amount']], [_label('Pad voices', bold=True), self._controls['pad_voice_count'], _label(''), _label('')]])
        stack = _vertical_stack([_card('Seed selection', 'Auto splits the population into one species per seed and evolves them side by side, so a run returns sixteen different pieces rather than sixteen takes of one.', selection_body), _card('Seed pool', 'Untick a seed to keep it out of this run.', seed_scroll), _card('Voicing', 'Blank fields let each seed use its own value.', voicing)], spacing=18.0)
        return _scrolling_form(stack)

    @objc.python_method
    def _make_variation_tab(self) -> NSView:
        for spec in project_state.VARIATION_FIELDS:
            self._controls[spec.key] = self._control_for_spec(spec)
        self._controls['groove'].setTarget_(self)
        self._controls['groove'].setAction_('grooveChoiceChanged:')
        groove_grid = _grid([[_label('Groove', bold=True), self._controls['groove']], [_label('Groove drift rate', bold=True), self._controls['groove_mutation_rate']]])
        self._groove_detail = self._detail_label()
        groove_columns = [_checkbox_column('included', '', 24), _text_column('label', 'Groove', 160, editable=False), _text_column('bass', 'Bass', 100, editable=False), _text_column('kick', 'Kick on', 150, editable=False), _text_column('hats', 'Hats', 70, editable=False)]
        self._groove_table, groove_scroll = _scrolling_table(groove_columns, self, self, height=200.0)
        self._groove_table.setIdentifier_('grooves')
        explore = _grid([[_label('Tempo drift (BPM)', bold=True), self._controls['tempo_drift_bpm']], [_label(''), self._controls['explore_rule_sets']], [_label(''), self._controls['explore_ca']], [_label(''), self._controls['explore_phrase_length']], [_label(''), self._controls['explore_octave_range']]])
        stack = _vertical_stack([_card('Groove', 'The rhythmic axis. Auto pairs each harmonic seed with a different groove so two variations differ in surface rhythm as well as in chord field.', _vertical_stack([groove_grid, self._groove_detail], spacing=14.0)), _card('Groove pool', 'Untick a groove to keep it out of this run.', groove_scroll), _card('Exploration', 'How far the search may roam from the values written on the Advanced tab. Switch one off to pin that value for every candidate.', explore)], spacing=18.0)
        return _scrolling_form(stack)

    @objc.python_method
    def _make_advanced_tab(self) -> NSView:
        cards = []
        for group in project_state.FIELD_GROUPS:
            if group.key in {'harmony', 'variation'}:
                continue
            rows = []
            pair: List[Any] = []
            for spec in group.fields:
                control = self._control_for_spec(spec)
                self._controls[spec.key] = control
                pair.extend([_label('' if spec.kind == 'bool' else spec.label, bold=True), control])
                if len(pair) == 4:
                    rows.append(pair)
                    pair = []
            if pair:
                pair.extend([_label(''), _label('')])
                rows.append(pair)
            cards.append(_card(group.title, group.subtitle, _grid(rows)))
        return _scrolling_form(_vertical_stack(cards, spacing=18.0))

    @objc.python_method
    def _make_variations_tab(self) -> NSView:
        columns = [_text_column(key, title, width, editable=False) for key, title, width in VARIATION_COLUMNS]
        self._variation_table, scroll = _scrolling_table(columns, self, self, height=340.0)
        self._variation_table.setIdentifier_('variations')
        buttons = _row([_push_button('Export All Songs...', self, 'exportAllVariations:')], spacing=8.0)
        self._variation_detail = self._detail_label()
        self._variation_detail.setStringValue_('Press ⌘R to generate. Each row is the best arrangement one harmonic seed produced, paired with its own groove.')
        stack = _vertical_stack([_card('Generated songs', 'The best arrangement each harmonic seed produced in the last run.', _vertical_stack([scroll, buttons, self._variation_detail], spacing=12.0))], spacing=18.0)
        return _scrolling_form(stack)

    @objc.python_method
    def _control_for_spec(self, spec) -> Any:
        if spec.kind == 'bool':
            return _checkbox(spec.label, True, self, 'noop:')
        if spec.kind == 'choice':
            return _popup(spec.choices, spec.choices[0] if spec.choices else '', 180)
        return _text_field('', 96)

    @objc.python_method
    def _install_toolbar(self) -> None:
        self._toolbar_items = {'open': ('Open', 'openDocument:', 'folder', 'Open an Oriondrive project'), 'save': ('Save', 'saveDocument:', 'square.and.arrow.down', 'Save this project'), 'generate': ('Generate', 'generate:', 'wand.and.stars', 'Evolve one arrangement per harmonic seed'), 'exportAll': ('Export All', 'exportAllVariations:', 'square.and.arrow.up', 'Write every generated song to a folder')}
        toolbar = NSToolbar.alloc().initWithIdentifier_('OriondriveToolbar')
        toolbar.setDelegate_(self)
        toolbar.setAllowsUserCustomization_(True)
        toolbar.setDisplayMode_(1)
        self._window.setToolbar_(toolbar)
        try:
            self._window.setToolbarStyle_(2)
        except AttributeError:
            pass

    def toolbarAllowedItemIdentifiers_(self, toolbar):
        return list(self._toolbar_items) + ['NSToolbarFlexibleSpaceItem', 'NSToolbarSpaceItem']

    def toolbarDefaultItemIdentifiers_(self, toolbar):
        return ['open', 'save', 'NSToolbarFlexibleSpaceItem', 'generate', 'exportAll']

    def toolbar_itemForItemIdentifier_willBeInsertedIntoToolbar_(self, toolbar, identifier, flag):
        if identifier not in self._toolbar_items:
            return None
        title, action, symbol, tooltip = self._toolbar_items[identifier]
        item = NSToolbarItem.alloc().initWithItemIdentifier_(identifier)
        item.setLabel_(title)
        item.setPaletteLabel_(title)
        item.setToolTip_(tooltip)
        item.setTarget_(self)
        item.setAction_(action)
        image = NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol, title)
        if image is not None:
            item.setImage_(image)
        try:
            item.setBordered_(True)
        except AttributeError:
            pass
        return item

    @objc.python_method
    def build_menu(self) -> NSMenu:
        main = NSMenu.alloc().init()
        app_item = NSMenuItem.alloc().init()
        main.addItem_(app_item)
        app_menu = NSMenu.alloc().init()
        app_menu.addItemWithTitle_action_keyEquivalent_('About Oriondrive', 'orderFrontStandardAboutPanel:', '')
        app_menu.addItem_(NSMenuItem.separatorItem())
        app_menu.addItemWithTitle_action_keyEquivalent_('Hide Oriondrive', 'hide:', 'h')
        app_menu.addItemWithTitle_action_keyEquivalent_('Hide Others', 'hideOtherApplications:', '')
        app_menu.addItem_(NSMenuItem.separatorItem())
        app_menu.addItemWithTitle_action_keyEquivalent_('Quit Oriondrive', 'terminate:', 'q')
        app_item.setSubmenu_(app_menu)
        file_item = NSMenuItem.alloc().init()
        main.addItem_(file_item)
        file_menu = NSMenu.alloc().initWithTitle_('File')
        for title, action, key in (('New', 'newDocument:', 'n'), ('Open...', 'openDocument:', 'o'), (None, None, None), ('Save', 'saveDocument:', 's'), ('Save As...', 'saveDocumentAs:', 'S'), (None, None, None), ('Export All Songs...', 'exportAllVariations:', 'e')):
            if title is None:
                file_menu.addItem_(NSMenuItem.separatorItem())
                continue
            entry = file_menu.addItemWithTitle_action_keyEquivalent_(title, action, key)
            entry.setTarget_(self)
        file_item.setSubmenu_(file_menu)
        edit_item = NSMenuItem.alloc().init()
        main.addItem_(edit_item)
        edit_menu = NSMenu.alloc().initWithTitle_('Edit')
        for title, action, key in (('Undo', 'undo:', 'z'), ('Redo', 'redo:', 'Z'), (None, None, None), ('Cut', 'cut:', 'x'), ('Copy', 'copy:', 'c'), ('Paste', 'paste:', 'v'), ('Select All', 'selectAll:', 'a')):
            if title is None:
                edit_menu.addItem_(NSMenuItem.separatorItem())
                continue
            edit_menu.addItemWithTitle_action_keyEquivalent_(title, action, key)
        edit_item.setSubmenu_(edit_menu)
        generate_item = NSMenuItem.alloc().init()
        main.addItem_(generate_item)
        generate_menu = NSMenu.alloc().initWithTitle_('Generate')
        run = generate_menu.addItemWithTitle_action_keyEquivalent_('Generate', 'generate:', 'r')
        run.setTarget_(self)
        generate_menu.addItem_(NSMenuItem.separatorItem())
        for index, key in enumerate(TAB_KEYS):
            entry = generate_menu.addItemWithTitle_action_keyEquivalent_(f'Show {TAB_TITLES[key]}', 'showTab:', str(index + 1))
            entry.setTarget_(self)
            entry.setTag_(index)
        generate_item.setSubmenu_(generate_menu)
        window_item = NSMenuItem.alloc().init()
        main.addItem_(window_item)
        window_menu = NSMenu.alloc().initWithTitle_('Window')
        window_menu.addItemWithTitle_action_keyEquivalent_('Minimize', 'performMiniaturize:', 'm')
        window_menu.addItemWithTitle_action_keyEquivalent_('Zoom', 'performZoom:', '')
        window_item.setSubmenu_(window_menu)
        NSApplication.sharedApplication().setWindowsMenu_(window_menu)
        return main

    @objc.python_method
    def load_preset(self, template: str) -> None:
        try:
            project = project_state.preset_project(template)
        except ValueError as exc:
            self.set_status(str(exc))
            return
        self._project_path = None
        self.apply_project(project)
        self.set_status(f'Loaded preset “{project.title}”.')

    @objc.python_method
    def apply_project(self, project) -> None:
        values = project_state.project_to_gui_state(project)
        self._sections = values.pop('sections')
        self._seed_pool = list(values.pop('seed_pool'))
        self._groove_pool = list(values.pop('groove_pool'))
        for key, value in values.items():
            control = self._controls.get(key)
            if control is None:
                continue
            self._set_control_value(control, key, value)
        self._reload_seed_rows()
        self._reload_groove_rows()
        self._section_table.reloadData()
        self._update_seed_detail()
        self._update_groove_detail()
        self._update_form_detail()

    @objc.python_method
    def _set_control_value(self, control, key: str, value: Any) -> None:
        if isinstance(control, NSPopUpButton):
            title = project_state.GENRE_LABELS.get(value, value) if key == 'genre' else value
            title = '—' if title == '' else str(title)
            if control.itemWithTitle_(title) is not None:
                control.selectItemWithTitle_(title)
            return
        if isinstance(control, NSButton):
            control.setState_(1 if value else 0)
            return
        control.setStringValue_(str(value))

    @objc.python_method
    def _control_value(self, control, key: str) -> Any:
        if isinstance(control, NSPopUpButton):
            title = control.titleOfSelectedItem() or ''
            if key == 'genre':
                for value, label in project_state.GENRE_LABELS.items():
                    if label == title:
                        return value
            return '' if title == '—' else title
        if isinstance(control, NSButton):
            return control.state() == 1
        return control.stringValue()

    @objc.python_method
    def current_values(self) -> Dict[str, Any]:
        values: Dict[str, Any] = {'seed_pool': list(self._seed_pool), 'groove_pool': list(self._groove_pool)}
        for key, control in self._controls.items():
            values[key] = self._control_value(control, key)
        return values

    @objc.python_method
    def current_project(self):
        return project_state.gui_state_to_project(self.current_values(), self._sections)

    @objc.python_method
    def _reload_seed_rows(self) -> None:
        genre = self._control_value(self._controls['genre'], 'genre') if 'genre' in self._controls else 'classic_trance'
        self._seed_rows = project_state.seed_display_rows(genre, self._seed_pool)
        if hasattr(self, '_seed_table'):
            self._seed_table.reloadData()

    @objc.python_method
    def _reload_groove_rows(self) -> None:
        genre = self._control_value(self._controls['genre'], 'genre') if 'genre' in self._controls else 'classic_trance'
        self._groove_rows = project_state.groove_display_rows(genre, self._groove_pool)
        if hasattr(self, '_groove_table'):
            self._groove_table.reloadData()

    @objc.python_method
    def _update_seed_detail(self) -> None:
        if not hasattr(self, '_seed_detail'):
            return
        name = self._control_value(self._controls['harmonic_seed'], 'harmonic_seed')
        self._seed_detail.setStringValue_(project_state.seed_detail_text(name or AUTO_SEED))

    @objc.python_method
    def _update_groove_detail(self) -> None:
        if not hasattr(self, '_groove_detail'):
            return
        name = self._control_value(self._controls['groove'], 'groove')
        self._groove_detail.setStringValue_(project_state.groove_detail_text(name or AUTO_GROOVE))

    @objc.python_method
    def set_status(self, message: str, busy: bool=False) -> None:
        self._status.setStringValue_(message)
        self._busy = busy
        if busy:
            self._spinner.startAnimation_(None)
        else:
            self._spinner.stopAnimation_(None)

    @objc.python_method
    def _size_tables(self) -> None:
        for table in (self._seed_table, self._groove_table, self._variation_table):
            scroll = table.enclosingScrollView()
            if scroll is None:
                continue
            key = str(table.identifier())
            columns = list(table.tableColumns())
            if key not in self._table_widths:
                self._table_widths[key] = [column.width() for column in columns]
            designed_widths = self._table_widths[key]
            available = scroll.contentView().frame().size.width - table.intercellSpacing().width * len(columns)
            if available <= 0:
                continue
            fixed = [index for index, column in enumerate(columns) if column.minWidth() >= column.maxWidth()]
            reserved = sum((designed_widths[index] for index in fixed))
            flexible_total = sum((width for index, width in enumerate(designed_widths) if index not in fixed)) or 1.0
            scale = max(0.4, (available - reserved) / flexible_total)
            for index, column in enumerate(columns):
                if index in fixed:
                    continue
                column.setWidth_(max(column.minWidth(), designed_widths[index] * scale))
            excess = sum((column.width() for column in columns)) - available
            if excess > 0:
                widest = max((columns[index] for index in range(len(columns)) if index not in fixed), key=lambda column: column.width())
                widest.setWidth_(max(widest.minWidth(), widest.width() - excess))
            table.setFrameSize_(NSSize(scroll.contentView().frame().size.width, table.frame().size.height))

    @objc.python_method
    def _select_tab(self, key: str) -> None:
        self._tabs.selectTabViewItemWithIdentifier_(key)
        self._size_tables()

    def noop_(self, sender):
        return None

    def genreChanged_(self, sender):
        self._reload_seed_rows()
        self._reload_groove_rows()
        self._update_form_detail()

    def seedChoiceChanged_(self, sender):
        self._update_seed_detail()

    def grooveChoiceChanged_(self, sender):
        self._update_groove_detail()

    def showTab_(self, sender):
        index = int(sender.tag())
        if 0 <= index < len(TAB_KEYS):
            self._select_tab(TAB_KEYS[index])
            self._sync_sidebar_selection(TAB_KEYS[index])

    def newDocument_(self, sender):
        self.load_preset('classic_trance')

    def openDocument_(self, sender):
        panel = NSOpenPanel.openPanel()
        panel.setAllowsMultipleSelection_(False)
        panel.setCanChooseDirectories_(False)
        panel.setMessage_('Open an Oriondrive project')
        _allow_extensions(panel, ['ori'])
        if panel.runModal() != 1:
            return
        path = Path(panel.URL().path())
        try:
            project = load_ori(path)
        except ValueError as exc:
            self.set_status(str(exc))
            return
        self._project_path = path
        self.apply_project(project)
        self.set_status(f'Opened {path}')

    def saveDocument_(self, sender):
        if self._project_path is None:
            return self.saveDocumentAs_(sender)
        try:
            save_ori(self.current_project(), self._project_path)
        except ValueError as exc:
            self.set_status(str(exc))
            return
        self.set_status(f'Saved {self._project_path}')

    def saveDocumentAs_(self, sender):
        try:
            project = self.current_project()
        except ValueError as exc:
            self.set_status(str(exc))
            return
        panel = NSSavePanel.savePanel()
        panel.setMessage_('Save Oriondrive project')
        panel.setNameFieldStringValue_(project_state.default_project_filename(project.title))
        _allow_extensions(panel, ['ori'])
        if panel.runModal() != 1:
            return
        path = Path(panel.URL().path())
        try:
            save_ori(project, path)
        except ValueError as exc:
            self.set_status(str(exc))
            return
        self._project_path = path
        self.set_status(f'Saved {path}')

    def generate_(self, sender):
        if self._busy:
            return
        try:
            project = self.current_project()
        except ValueError as exc:
            self.set_status(str(exc))
            return
        self.set_status('Evolving one species per harmonic seed...', busy=True)
        threading.Thread(target=self._run_generation, args=(project,), daemon=True).start()

    @objc.python_method
    def _run_generation(self, project) -> None:
        try:
            selection = generate_project(project, allow_small_population=True, min_duration_seconds=DEFAULT_MIN_DURATION_SECONDS)
        except (RuntimeError, ValueError) as exc:
            AppHelper.callAfter(self._generation_failed, str(exc))
            return
        except Exception:
            AppHelper.callAfter(self._generation_failed, traceback.format_exc(limit=3))
            return
        AppHelper.callAfter(self._generation_finished, selection)

    @objc.python_method
    def _generation_failed(self, message: str) -> None:
        self.set_status(message, busy=False)

    @objc.python_method
    def _generation_finished(self, selection) -> None:
        self._selection = selection
        self._variations = selection.variations()
        self._variation_table.reloadData()
        self._select_tab('variations')
        self._sync_sidebar_selection('variations')
        winner = selection.winner
        grooves = len({candidate.groove for candidate in self._variations})
        tempos = len({candidate.genome.tempo for candidate in self._variations})
        self._variation_detail.setStringValue_(f'{len(self._variations)} variations across {len(selection.seed_pool)} harmonic seeds and {grooves} grooves, at {tempos} different tempos.\nSelect a row and press ⌘E to export it, or ⇧⌘E to write them all to a folder.')
        self.set_status(f'Done. {len(self._variations)} variations, best “{winner.harmonic_seed}” on “{winner.groove}” scoring {winner.final_score:.3f} at {winner.duration_seconds:.0f}s.', busy=False)

    def exportAllVariations_(self, sender):
        if self._selection is None:
            self.set_status('Generate first, then export.')
            return
        panel = NSOpenPanel.openPanel()
        panel.setCanChooseFiles_(False)
        panel.setCanChooseDirectories_(True)
        panel.setCanCreateDirectories_(True)
        panel.setPrompt_('Choose Folder')
        panel.setMessage_('Choose a folder for the seed variations')
        if panel.runModal() != 1:
            return
        directory = Path(panel.URL().path()) / default_variations_dir('oriondrive.mid').name
        try:
            results = write_seed_variations(self._selection, directory, min_duration_seconds=None)
            extras = self._write_optional_outputs(directory / 'oriondrive.mid')
        except (RuntimeError, ValueError) as exc:
            self.set_status(str(exc))
            return
        suffix = f" | {' | '.join(extras)}" if extras else ''
        self.set_status(f'Wrote {len(results)} songs to {directory}{suffix}')

    @objc.python_method
    def _write_optional_outputs(self, target: Path) -> List[str]:
        extras: List[str] = []
        if self._selection is None:
            return extras
        if self._controls['save_report'].state() == 1:
            report = write_fitness_report(self._selection, str(default_fitness_report_path(str(target))))
            extras.append(f'report {report.name}')
        if self._controls['save_candidates'].state() == 1:
            directory = default_candidate_output_dir(str(target))
            directory.mkdir(parents=True, exist_ok=True)
            for rank, candidate in enumerate(self._selection.ranked_candidates, start=1):
                write_midi(candidate.composition, directory / f'{rank:02d}_{candidate.candidate_id}.mid', min_duration_seconds=None)
            extras.append(f'candidates {directory.name}')
        return extras

    @objc.python_method
    def _selected_variation(self):
        if not self._variations:
            return None
        row = self._variation_table.selectedRow()
        if row < 0 or row >= len(self._variations):
            return None
        return self._variations[row]

    def addSection_(self, sender):
        self._sections.append(project_state.new_section())
        self._section_table.reloadData()
        self._section_table.selectRowIndexes_byExtendingSelection_(_index_set(len(self._sections) - 1), False)

    def deleteSection_(self, sender):
        row = self._section_table.selectedRow()
        if len(self._sections) <= 1:
            self.set_status('A project needs at least one section.')
            return
        if 0 <= row < len(self._sections):
            del self._sections[row]
            self._section_table.reloadData()

    def moveSectionUp_(self, sender):
        self._move_section(-1)

    def moveSectionDown_(self, sender):
        self._move_section(1)

    @objc.python_method
    def _move_section(self, delta: int) -> None:
        row = self._section_table.selectedRow()
        target = row + delta
        if 0 <= row < len(self._sections) and 0 <= target < len(self._sections):
            self._sections[row], self._sections[target] = (self._sections[target], self._sections[row])
            self._section_table.reloadData()
            self._section_table.selectRowIndexes_byExtendingSelection_(_index_set(target), False)

    def numberOfRowsInTableView_(self, table):
        identifier = table.identifier()
        if identifier == 'sections':
            return len(self._sections)
        if identifier == 'seeds':
            return len(self._seed_rows)
        if identifier == 'grooves':
            return len(self._groove_rows)
        if identifier == 'variations':
            return len(self._variations)
        return 0

    def tableView_objectValueForTableColumn_row_(self, table, column, row):
        identifier = table.identifier()
        key = str(column.identifier())
        if identifier == 'sections':
            return self._section_cell_value(key, row)
        if identifier == 'seeds':
            seed = self._seed_rows[row]
            if key == 'included':
                return 1 if seed['included'] else 0
            return str(seed.get(key, ''))
        if identifier == 'grooves':
            groove = self._groove_rows[row]
            if key == 'included':
                return 1 if groove['included'] else 0
            return str(groove.get(key, ''))
        if identifier == 'variations':
            return self._variation_cell_value(key, row)
        return ''

    @objc.python_method
    def _section_cell_value(self, key: str, row: int):
        section = self._sections[row]
        value = section.get(key, '')
        role_group = _role_group_for(key)
        if role_group is not None:
            options = project_state.ROLE_OPTIONS[role_group]
            return options.index(value) if value in options else 0
        return str(value)

    @objc.python_method
    def _variation_cell_value(self, key: str, row: int) -> str:
        candidate = self._variations[row]
        harmony = candidate.structure_map.get('harmony', {})
        if key == 'rank':
            return str(row + 1)
        if key == 'label':
            return str(harmony.get('harmonic_seed_label', candidate.harmonic_seed))
        if key == 'groove':
            return str(candidate.groove).replace('_', ' ').title()
        if key == 'mode':
            return str(harmony.get('mode', getattr(candidate.genome, 'scale', '')))
        if key == 'tempo':
            return str(getattr(candidate.genome, 'tempo', ''))
        if key == 'progression':
            return ' | '.join(harmony.get('progression', []))
        if key == 'score':
            return f'{candidate.final_score:.3f}'
        return ''

    def tableView_setObjectValue_forTableColumn_row_(self, table, value, column, row):
        identifier = table.identifier()
        key = str(column.identifier())
        if identifier == 'seeds' and key == 'included':
            self._toggle_pool(self._seed_pool, self._seed_rows[row]['name'], bool(value), 'harmonic seed')
            self._reload_seed_rows()
            return
        if identifier == 'grooves' and key == 'included':
            self._toggle_pool(self._groove_pool, self._groove_rows[row]['name'], bool(value), 'groove')
            self._reload_groove_rows()
            return
        if identifier != 'sections' or not 0 <= row < len(self._sections):
            return
        role_group = _role_group_for(key)
        if role_group is not None:
            options = project_state.ROLE_OPTIONS[role_group]
            index = int(value) if value is not None else 0
            self._sections[row][key] = options[index] if 0 <= index < len(options) else options[0]
            return
        text = str(value)
        if key == 'length_bars':
            try:
                self._sections[row][key] = int(float(text))
            except ValueError:
                self.set_status('Bars must be a whole number, and a multiple of 8.')
            return
        if key == 'energy':
            try:
                self._sections[row][key] = float(text)
            except ValueError:
                self.set_status('Energy must be a number between 0.0 and 1.0.')
            return
        self._sections[row][key] = text

    @objc.python_method
    def _toggle_pool(self, pool: List[str], name: str, include: bool, label: str) -> None:
        if include and name not in pool:
            pool.append(name)
        elif not include and name in pool:
            if len(pool) == 1:
                self.set_status(f'At least one {label} must stay in the pool.')
            else:
                pool.remove(name)

    def outlineView_numberOfChildrenOfItem_(self, outline, item):
        if item is None:
            return len(self._sidebar_roots)
        return len(_node(item).children)

    def outlineView_child_ofItem_(self, outline, index, item):
        children = self._sidebar_roots if item is None else _node(item).children
        return _wrap(children[index])

    def outlineView_isItemExpandable_(self, outline, item):
        return bool(_node(item).children)

    def outlineView_objectValueForTableColumn_byItem_(self, outline, column, item):
        return _node(item).title

    def outlineView_isGroupItem_(self, outline, item):
        return _node(item).kind == 'group'

    def outlineView_shouldSelectItem_(self, outline, item):
        return _node(item).kind != 'group'

    def outlineViewSelectionDidChange_(self, notification):
        outline = notification.object()
        row = outline.selectedRow()
        if row < 0:
            return
        node = _node(outline.itemAtRow_(row))
        if node.kind == 'tab':
            self._select_tab(node.key)
        elif node.kind == 'preset':
            self.load_preset(node.key)
            self._select_tab('song')

    @objc.python_method
    def _sync_sidebar_selection(self, tab_key: str) -> None:
        for row in range(self._outline.numberOfRows()):
            node = _node(self._outline.itemAtRow_(row))
            if node.kind == 'tab' and node.key == tab_key:
                self._outline.selectRowIndexes_byExtendingSelection_(_index_set(row), False)
                return

    def applicationDidFinishLaunching_(self, notification):
        application = NSApplication.sharedApplication()
        application.setMainMenu_(self.build_menu())
        self.build()
        self._outline.expandItem_expandChildren_(None, True)
        self._sync_sidebar_selection('song')
        application.activateIgnoringOtherApps_(True)

    def applicationShouldTerminateAfterLastWindowClosed_(self, application):
        return True

    def validateMenuItem_(self, item):
        action = item.action()
        if action == 'generate:':
            return not self._busy
        if action == 'exportAllVariations:':
            return self._selection is not None
        return True
_NODE_BOX: Dict[int, SidebarNode] = {}

class _NodeRef(NSObject):

    def initWithKey_(self, key):
        self = objc.super(_NodeRef, self).init()
        if self is None:
            return None
        self._key = int(key)
        return self

    def key(self):
        return self._key
_REF_CACHE: Dict[int, _NodeRef] = {}

def _wrap(node: SidebarNode) -> _NodeRef:
    key = id(node)
    _NODE_BOX[key] = node
    if key not in _REF_CACHE:
        _REF_CACHE[key] = _NodeRef.alloc().initWithKey_(key)
    return _REF_CACHE[key]

def _node(item) -> SidebarNode:
    return _NODE_BOX[item.key()]

def _role_group_for(key: str) -> Optional[str]:
    for column_key, _title, _width, role_group in SECTION_COLUMNS:
        if column_key == key:
            return role_group
    return None

def _index_set(index: int):
    from Foundation import NSIndexSet
    return NSIndexSet.indexSetWithIndex_(index)

def _allow_extensions(panel, extensions: List[str]) -> None:
    try:
        from UniformTypeIdentifiers import UTType
        types = [UTType.typeWithFilenameExtension_(extension) for extension in extensions]
        types = [item for item in types if item is not None]
        if types:
            panel.setAllowedContentTypes_(types)
            return
    except (ImportError, AttributeError):
        pass
    try:
        panel.setAllowedFileTypes_(extensions)
    except AttributeError:
        pass

def _application_icon() -> Optional[NSImage]:
    import sys
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
    for candidate in (base / 'assets' / 'Oriondrive.icns', base / 'Oriondrive.icns'):
        if candidate.exists():
            return NSImage.alloc().initWithContentsOfFile_(str(candidate))
    return None

def main() -> None:
    application = NSApplication.sharedApplication()
    application.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    icon = _application_icon()
    if icon is not None:
        application.setApplicationIconImage_(icon)
    controller = OriondriveController.alloc().init()
    application.setDelegate_(controller)
    globals()['_CONTROLLER'] = controller
    AppHelper.runEventLoop()
if __name__ == '__main__':
    main()
