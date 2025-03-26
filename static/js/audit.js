window.app = Vue.createApp({
  el: "#vue",
  mixins: [window.windowMixin],
  data: function () {
    return {
      auditEntries: [],
      auditTable: {
        columns: [
          {
            name: "id",
            align: "left",
            label: "ID",
            field: "id",
            sortable: true,
          },
          {
            name: "entry_id",
            align: "left",
            label: "Entry ID",
            field: "entry_id",
            sortable: true,
          },
          {
            name: "created_at",
            align: "left",
            label: "Created At",
            field: "created_at",
            format: (val) => LNbits.utils.formatDateString(val),
            sortable: true,
          },
          {
            name: "data",
            align: "left",
            label: "Data",
            field: "data",
            sortable: false,
          },
        ],
        pagination: {
          rowsPerPage: 10,
          page: 1,
          rowsNumber: 10,
        },
        search: "",
      },
      auditForm: {
        show: false,
        entryId: entry_id,
      },
    };
  },
  watch: {
    "auditTable.search": {
      handler() {
        this.getAuditEntriesPaginated();
      },
    },
  },
  methods: {
    getAuditEntriesPaginated: async function (props) {
      try {
        const params = LNbits.utils.prepareFilterQuery(this.auditTable, props);
        const { data } = await LNbits.api.request(
          "GET",
          `/auction_house/api/v1/audit/items` +
            `/${this.auditForm.entryId}/paginated?${params}`,
        );
        this.auditEntries = data.data;
        this.auditTable.pagination.rowsNumber = data.total;
      } catch (error) {
        LNbits.utils.notifyApiError(error);
      }
    },
  },
  created() {
    this.getAuditEntriesPaginated();
  },
});
