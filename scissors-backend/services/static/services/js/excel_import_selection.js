(() => {
  const form = document.getElementById('excel-preview-form');
  if (!form) return;

  const rows = [...form.querySelectorAll('input[name="selected_rows"]')];
  const selectAll = form.querySelector('#select-all-rows');
  const clearSelection = form.querySelector('#clear-selected-rows');
  const apply = form.querySelector('[name="apply_selected"]');
  const selectedCount = form.querySelector('#selected-count');
  if (!selectAll || !clearSelection || !apply) return;

  const updateButtons = () => {
    const selected = rows.filter((row) => row.checked).length;
    selectAll.disabled = rows.length === 0 || selected === rows.length;
    clearSelection.disabled = selected === 0;
    if (form.hasAttribute('data-reviewed')) {
      apply.disabled = form.dataset.reviewed !== 'true' || selected === 0;
    }
    if (selectedCount) selectedCount.textContent = `Выбрано строк: ${selected}`;
  };

  selectAll.addEventListener('click', () => {
    rows.forEach((row) => { row.checked = true; });
    updateButtons();
  });
  clearSelection.addEventListener('click', () => {
    rows.forEach((row) => { row.checked = false; });
    updateButtons();
  });
  rows.forEach((row) => row.addEventListener('change', updateButtons));
  if (!form.hasAttribute('data-reviewed')) {
    const review = form.querySelector('[name="review_matches"]');
    form.querySelectorAll('select[name^="match_"]').forEach((select) => {
      select.addEventListener('change', () => {
        const tableRow = select.closest('tr');
        const checkbox = tableRow?.querySelector('input[name="selected_rows"]');
        if (checkbox && select.value) checkbox.checked = true;
        if (review) {
          if (tableRow?.id) form.action = `#${tableRow.id}`;
          form.requestSubmit(review);
        }
      });
    });
  }
  updateButtons();
})();
