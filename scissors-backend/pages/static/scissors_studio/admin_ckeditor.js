(function () {
  'use strict';

  const PRESETS = {
    'Типографика': ['text-h3', 'text-h4', 'text-h5', 'text-subtitle1', 'text-body1', 'text-body2', 'text-caption', 'text-overline', 'text-weight-bold', 'text-weight-medium'],
    'Цвет': ['text-primary', 'text-dark', 'text-grey-7', 'text-grey-8', 'bg-grey-2'],
    'Выравнивание': ['text-left', 'text-center', 'text-right', 'text-justify'],
    'Отступы': ['q-mt-sm', 'q-mt-md', 'q-mb-md', 'q-mb-lg', 'q-my-md', 'q-pa-md'],
    'Классы проекта': ['site-page'],
  };
  const CLASS_NAME = /^[A-Za-z_][A-Za-z0-9_-]*$/;
  const BLOCK_TAGS = new Set([
    'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote',
    'div', 'section', 'article', 'ul', 'ol', 'li',
  ]);

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function selectedBlocks(editor) {
    const schema = editor.plugins.get('DataSchema');
    const support = editor.plugins.get('GeneralHtmlSupport');
    const result = new Map();
    for (const selected of editor.model.document.selection.getSelectedBlocks()) {
      for (const block of selected.getAncestors({ includeSelf: true }).reverse()) {
        if (block.is('rootElement')) continue;
        const definition = schema.getDefinitionsForModel(block.name).find(
          (item) => typeof item.view === 'string' && BLOCK_TAGS.has(item.view),
        );
        if (!definition) continue;
        const attribute = support.getGhsAttributeNameForElement(definition.view);
        if (editor.model.schema.checkAttribute(block, attribute)) {
          result.set(block, { block, tag: definition.view, attribute });
          break;
        }
      }
    }
    return [...result.values()];
  }

  function classNames(blockInfo) {
    return blockInfo ? [...(blockInfo.block.getAttribute(blockInfo.attribute)?.classes || [])] : [];
  }

  function attachClassControl(editor) {
    if (!editor.plugins.has('GeneralHtmlSupport')) return;
    let dropdown = Array.from(editor.ui.view.toolbar.items).find(
      (item) => typeof item.class === 'string' && item.class.includes('ck-style-dropdown'),
    );
    if (!dropdown) {
      dropdown = editor.ui.componentFactory.create('style');
      editor.ui.view.toolbar.items.add(dropdown);
    }
    // The built-in Style command only handles fixed definitions. The panel
    // below also handles custom classes through GeneralHtmlSupport.
    dropdown.unbind('isEnabled');
    const sourceEditing = editor.plugins.get('SourceEditing');
    const updateEnabled = () => {
      dropdown.isEnabled = !editor.isReadOnly && !sourceEditing.isSourceEditingMode;
    };
    editor.on('change:isReadOnly', updateEnabled);
    sourceEditing.on('change:isSourceEditingMode', updateEnabled);
    updateEnabled();
    dropdown.buttonView.unbind('label');
    dropdown.buttonView.label = 'CSS-классы';
    dropdown.buttonView.withText = true;

    dropdown.once('change:isOpen', () => {
      const BaseView = Object.getPrototypeOf(dropdown.panelView.constructor);
      const view = new BaseView(editor.locale);
      view.setTemplate({ tag: 'div', attributes: { class: ['ck', 'sc-class-control'] } });
      view.render();

      const heading = element('strong', 'sc-class-control__heading', 'Классы выбранного блока');
      const preset = element('select', 'sc-class-control__field');
      preset.setAttribute('aria-label', 'Готовые CSS-классы');
      const presetPlaceholder = element('option', '', 'Выберите класс…');
      presetPlaceholder.value = '';
      preset.append(presetPlaceholder);
      for (const [category, names] of Object.entries(PRESETS)) {
        const group = element('optgroup');
        group.label = category;
        for (const name of names) {
          const option = element('option', '', name);
          option.value = name;
          group.append(option);
        }
        preset.append(group);
      }

      const classInput = element('input', 'sc-class-control__field');
      classInput.type = 'text';
      classInput.placeholder = 'Свой CSS-класс';
      classInput.setAttribute('aria-label', 'Класс для добавления или замены');
      preset.addEventListener('change', () => { classInput.value = preset.value; });

      const existing = element('select', 'sc-class-control__field');
      existing.setAttribute('aria-label', 'Существующий класс для замены или удаления');
      const add = element('button', '', 'Добавить');
      const replace = element('button', '', 'Заменить');
      const remove = element('button', '', 'Удалить');
      const setInput = element('input', 'sc-class-control__field');
      setInput.type = 'text';
      setInput.placeholder = 'Все классы через пробел';
      setInput.setAttribute('aria-label', 'Полный набор классов выбранного блока');
      const saveSet = element('button', '', 'Сохранить набор');
      const status = element('div', 'sc-class-control__status');
      status.setAttribute('role', 'status');

      for (const button of [add, replace, remove, saveSet]) button.type = 'button';
      function refresh() {
        const blocks = selectedBlocks(editor);
        const previous = existing.value;
        const classes = classNames(blocks[0]);
        const existingPlaceholder = element('option', '', 'Выберите существующий класс…');
        existingPlaceholder.value = '';
        existing.replaceChildren(existingPlaceholder);
        for (const name of classes) {
          const option = element('option', '', name);
          option.value = name;
          existing.append(option);
        }
        if (classes.includes(previous)) existing.value = previous;
        if (document.activeElement !== setInput) setInput.value = classes.join(' ');
        status.textContent = blocks.length ? '' : 'Выберите текстовый блок в редакторе.';
      }

      function apply(action) {
        const blocks = selectedBlocks(editor);
        const name = classInput.value.trim();
        const oldName = existing.value;
        if (!blocks.length) { refresh(); return; }
        if (action !== 'remove' && !CLASS_NAME.test(name)) {
          status.textContent = 'Введите один корректный CSS-класс.';
          return;
        }
        if ((action === 'replace' || action === 'remove') && !oldName) {
          status.textContent = 'Выберите существующий класс.';
          return;
        }
        const support = editor.plugins.get('GeneralHtmlSupport');
        for (const { block, tag } of blocks) {
          if (action === 'replace' || action === 'remove') {
            support.removeModelHtmlClass(tag, oldName, block);
          }
          if (action === 'add' || action === 'replace') {
            support.addModelHtmlClass(tag, name, block);
          }
        }
        refresh();
      }

      add.addEventListener('click', () => apply('add'));
      replace.addEventListener('click', () => apply('replace'));
      remove.addEventListener('click', () => apply('remove'));
      saveSet.addEventListener('click', () => {
        const blocks = selectedBlocks(editor);
        if (!blocks.length) { refresh(); return; }
        const desired = [...new Set(setInput.value.trim().split(/\s+/).filter(Boolean))];
        if (desired.some((name) => !CLASS_NAME.test(name))) {
          status.textContent = 'В наборе есть некорректный CSS-класс.';
          return;
        }
        const support = editor.plugins.get('GeneralHtmlSupport');
        for (const info of blocks) {
          const current = classNames(info);
          for (const name of current) {
            if (!desired.includes(name)) support.removeModelHtmlClass(info.tag, name, info.block);
          }
          for (const name of desired) {
            if (!current.includes(name)) support.addModelHtmlClass(info.tag, name, info.block);
          }
        }
        refresh();
      });

      const actions = element('div', 'sc-class-control__actions');
      actions.append(add, replace, remove);
      const setActions = element('div', 'sc-class-control__actions');
      setActions.append(saveSet);
      view.element.append(heading, preset, classInput, existing, actions, setInput, setActions, status);
      view.focus = () => preset.focus();
      view.focusLast = () => saveSet.focus();
      dropdown.panelView.children.add(view);
      editor.model.document.selection.on('change:range', refresh);
      editor.model.document.on('change:data', refresh);
      refresh();
    });
  }

  function register() {
    if (typeof window.ckeditorRegisterCallback !== 'function') return;
    for (const textarea of document.querySelectorAll('textarea.django_ckeditor_5')) {
      window.ckeditorRegisterCallback(textarea.id, attachClassControl);
      const editor = window.editors?.[textarea.id];
      if (editor) attachClassControl(editor);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', register);
  } else {
    register();
  }
})();
