(() => {
  const form = document.getElementById('excel-preview-form');
  if (!form) return;

  const rows = [...form.querySelectorAll('input[name="selected_rows"]')];
  const selectAll = form.querySelector('#select-all-rows');
  const clearSelection = form.querySelector('#clear-selected-rows');
  const apply = form.querySelector('#apply-selected-rows');
  const selectedCount = form.querySelector('#selected-count');
  const progress = form.querySelector('#import-progress');
  const review = form.querySelector('[name="review_matches"]');

  const updateSelection = () => {
    const selected = rows.filter((row) => row.checked).length;
    if (selectAll) selectAll.disabled = selected === rows.length;
    if (clearSelection) clearSelection.disabled = selected === 0;
    if (selectedCount) selectedCount.textContent = `Выбрано строк: ${selected}`;
  };

  selectAll?.addEventListener('click', () => {
    rows.forEach((row) => { row.checked = true; });
    updateSelection();
  });
  clearSelection?.addEventListener('click', () => {
    rows.forEach((row) => { row.checked = false; });
    updateSelection();
  });
  rows.forEach((row) => row.addEventListener('change', updateSelection));

  form.querySelectorAll('select[name^="match_"]').forEach((select) => {
    select.addEventListener('change', () => {
      const tableRow = select.closest('tr');
      const checkbox = tableRow?.querySelector('input[name="selected_rows"]');
      if (checkbox && select.value) checkbox.checked = true;
      updateSelection();
      if (review) {
        if (tableRow?.id) form.action = `${window.location.pathname}#${tableRow.id}`;
        form.requestSubmit(review);
      }
    });
  });

  form.addEventListener('submit', (event) => {
    if (event.submitter !== apply) return;
    if (progress) progress.hidden = false;
    if (apply) apply.textContent = 'Импорт выполняется…';
  });
  updateSelection();
})();
