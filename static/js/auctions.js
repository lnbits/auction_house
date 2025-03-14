window.app = Vue.createApp({
  el: "#vue",
  mixins: [window.windowMixin],
  data: function () {
    return {
      auctionItems: [],
      itemFormDialog: {
        show: false,
        data: {
          name: "",
          description: "",
          ask_price: 0,
        },
      },
      onlyMyItems: false,
      showInactiveItems: false,
      itemsTable: {
        columns: [
          {
            name: "active",
            align: "left",
            label: "",
            field: "active",
            sortable: false,
            format: (_, row) => (row.active === true ? "🟢" : "⚪"),
          },
          {
            name: "name",
            align: "left",
            label: "Name",
            field: "name",
            sortable: true,
          },
          {
            name: "description",
            align: "left",
            label: "Description",
            field: "description",
            sortable: false,
            format: (val) => (val || "").substring(0, 50),
          },
          {
            name: "ask_price",
            align: "left",
            label: "Ask Price",
            field: "ask_price",
            sortable: true,
            format: (_, row) =>
              LNbits.utils.formatCurrency(row.ask_price, row.currency),
          },
          {
            name: "current_price",
            align: "left",
            label: "Current Price",
            field: "current_price",
            sortable: true,
            format: (_, row) =>
              LNbits.utils.formatCurrency(row.current_price, row.currency),
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
            name: "expires_at",
            align: "left",
            label: "Expires At",
            field: "expires_at",
            format: (val) => LNbits.utils.formatDateString(val),
            sortable: true,
          },
          {
            name: "id",
            align: "left",
            label: "ID",
            field: "id",
            sortable: true,
          },
        ],
        pagination: {
          rowsPerPage: 10,
          page: 1,
          rowsNumber: 10,
        },
      },

      auctionRoomForm: {
        show: false,
        isUserAuthenticated: is_user_authenticated,
        isUserRoomOwner: is_user_room_owner,
        data: auction_room,
      },
    };
  },
  methods: {
    getAuctionItemsPaginated: async function (props) {
      try {
        const params = LNbits.utils.prepareFilterQuery(this.itemsTable, props);
        const auctionRoomId = this.auctionRoomForm.data.id;
        const { data } = await LNbits.api.request(
          "GET",
          `/auction_house/api/v1/items/${auctionRoomId}` +
            `/paginated?only_mine=${this.onlyMyItems}` +
            `&include_inactive=${this.showInactiveItems}&${params}`,
        );
        this.auctionItems = data.data;
        this.itemsTable.pagination.rowsNumber = data.total;
      } catch (error) {
        LNbits.utils.notifyApiError(error);
      }
    },

    addAuctionItem: async function () {
      const auctionRoomId = this.auctionRoomForm.data.id;
      try {
        await LNbits.api.request(
          "POST",
          `/auction_house/api/v1/${auctionRoomId}/items`, // items/{}
          null,
          this.itemFormDialog.data,
        );
        this.itemFormDialog.show = false;
        this.$q.notify({
          type: "positive",
          message: "Auction Item added!",
        });
        this.getAuctionItemsPaginated();
      } catch (error) {
        LNbits.utils.notifyApiError(error);
      }
    },
    showAddNewAuctionItemDialog: function () {
      this.itemFormDialog.show = true;
      this.itemFormDialog.data = {
        name: "",
        description: "",
        ask_price: 0,
      };
    },
    formatCurrency(amount, currency) {
      try {
        return LNbits.utils.formatCurrency(amount, currency);
      } catch (e) {
        console.error(e);
        return `${amount} ???`;
      }
    },
  },
  created() {
    this.getAuctionItemsPaginated();
  },
});
