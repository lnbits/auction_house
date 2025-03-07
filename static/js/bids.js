window.app = Vue.createApp({
  el: "#vue",
  mixins: [window.windowMixin],
  data: function () {
    return {
      auctionItems: [],
      timeLeft: {
        days: 0,
        hours: 0,
        minutes: 0,
        seconds: 0,
      },
      bidRequest: null,
      bidPrice: 0,
      bidMemo: "",
      showBidRequestQrCode: false,
      itemFormDialog: {
        show: false,
        data: {
          name: "",
          description: "",
          starting_price: 0,
        },
      },
      itemsTable: {
        columns: [
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
            name: "starting_price",
            align: "left",
            label: "Sarting Price",
            field: "starting_price",
            sortable: true,
            format: (_, row) =>
              LNbits.utils.formatCurrency(row.starting_price, row.currency),
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
        ],
        pagination: {
          rowsPerPage: 10,
          page: 1,
          rowsNumber: 10,
        },
      },
      bidForm: {
        show: false,
        isUserAuthenticated: is_user_authenticated,
        data: auction_item,
      },
    };
  },
  methods: {
    getAuctionItemsPaginated: async function (props) {
      try {
        const params = LNbits.utils.prepareFilterQuery(this.itemsTable, props);
        const auctionRoomId = this.bidForm.data.id;
        const { data, total } = await LNbits.api.request(
          "GET",
          `/auction_house/api/v1/${auctionRoomId}/items/paginated?${params}`,
        );

        this.auctionItems = data.data;
      } catch (error) {
        LNbits.utils.notifyApiError(error);
      }
    },

    addAuctionItem: async function () {
      const auctionRoomId = this.bidForm.data.id;
      try {
        await LNbits.api.request(
          "POST",
          `/auction_house/api/v1/${auctionRoomId}/items`,
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
    placeBid: async function () {
      const auctionItemId = this.bidForm.data.id;
      try {
        const {data} = await LNbits.api.request(
          "PUT",
          `/auction_house/api/v1/bids/${auctionItemId}`,
          null,
          {
            amount: this.bidPrice,
            memo: this.bidMemo,
          },
        );
        console.log("### placeBid", data);
        this.bidRequest = data;
        this.showBidRequestQrCode = true
        this.$q.notify({
          type: "positive",
          message: "Bid queued!",
          caption: "Pay the invoice to confirm the bid",
        });
        // this.getAuctionItemsPaginated();
      } catch (error) {
        LNbits.utils.notifyApiError(error);
      }
    },
    showAddNewAuctionItemDialog: function () {
      this.itemFormDialog.show = true;
      this.itemFormDialog.data = {
        name: "",
        description: "",
        starting_price: 0,
      };
    },
    initTimeLeft: function (item) {
      setInterval(() => {
        item.time_left_seconds -= 1;
        const duration = moment.utc(item.time_left_seconds * 1000);
        this.timeLeft = {
          days: duration.format("DDD"),
          hours: duration.format("HH"),
          minutes: duration.format("mm"),
          seconds: duration.format("ss"),
        };
        this.currentPrice = LNbits.utils.formatCurrency(
          item.current_price,
          item.currency,
        );
        this.bidPrice = item.next_min_bid;
      }, 1000);
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
    console.log("### created bidForm", this.bidForm);

    this.initTimeLeft(this.bidForm.data);
    this.getAuctionItemsPaginated();
  },
});
