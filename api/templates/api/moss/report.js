// Clicking a sortable column sorts its table by it: highest first, and lowest
// first on a second click.
document.querySelectorAll("th.sortable").forEach((th) => {
  th.addEventListener("click", () => {
    const descending = th.dataset.order !== "desc";
    for (const other of th.parentNode.cells) delete other.dataset.order;
    th.dataset.order = descending ? "desc" : "asc";
    const body = th.closest("table").tBodies[0];
    const value = (row) => parseFloat(row.cells[th.cellIndex].textContent);
    const rows = [...body.rows];
    rows.sort((a, b) => (descending ? value(b) - value(a) : value(a) - value(b)));
    for (const row of rows) body.appendChild(row);
  });
});
