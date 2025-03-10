window.app = Vue.createApp({
  el: "#vue",
  mixins: [window.windowMixin],
  data: function () {
    return {
      bidsList: [],
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

      bidsTable: {
        columns: [
          {
            name: "id",
            align: "left",
            label: "Id",
            field: "id",
            sortable: true,
          },
          {
            name: "memo",
            align: "left",
            label: "Memo",
            field: "memo",
            sortable: true,
          },
          {
            name: "created_at",
            align: "left",
            label: "Date",
            field: "created_at",
            format: (val) => LNbits.utils.formatDateString(val),
            sortable: true,
          },
          {
            name: "amount",
            align: "left",
            label: "Amount",
            field: "amount",
            sortable: true,
            format: (_, row) =>
              LNbits.utils.formatCurrency(row.amount, row.currency),
          },
          {
            name: "amount_sat",
            align: "left",
            label: "Amount Sat",
            field: "amount_sat",
            sortable: true,
            format: (_, row) =>
              LNbits.utils.formatCurrency(row.amount_sat, "sat"),
          },
        ],
        pagination: {
          sortBy: "amount",
          rowsPerPage: 10,
          page: 1,
          descending: true,
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
    getBidsPaginated: async function (props) {
      try {
        const params = LNbits.utils.prepareFilterQuery(this.bidsTable, props);
        const auctionItemId = this.bidForm.data.id;
        const { data, total } = await LNbits.api.request(
          "GET",
          `/auction_house/api/v1/bids/${auctionItemId}/paginated?${params}`,
        );

        this.bidsList = data.data;
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
        const { data } = await LNbits.api.request(
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
        this.showBidRequestQrCode = true;
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
    const item = this.bidForm.data;
    this.initTimeLeft(item);
    this.getBidsPaginated();
    this.currentPrice = LNbits.utils.formatCurrency(
      item.current_price,
      item.currency,
    );
    this.bidPrice = item.next_min_bid;
  },
});
