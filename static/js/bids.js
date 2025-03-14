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
      lnAddress: "",
      bidMemo: "",
      onlyMyBids: false,
      showUnpaidBids: false,
      showBidRequestQrCode: false,
      itemFormDialog: {
        show: false,
        data: {
          name: "",
          description: "",
          ask_price: 0,
        },
      },

      bidsTable: {
        columns: [
          {
            name: "paid",
            align: "left",
            label: "",
            field: "paid",
            sortable: false,
            format: (_, row) =>
              row.paid === true ? (row.higher_bid_made ? "✔" : "✅") : "❌",
          },
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
        isUserRoomOwner: is_user_room_owner,
        isAuctionType: is_auction_type,
        data: auction_item,
      },
    };
  },
  methods: {
    getBidsPaginated: async function (props) {
      try {
        const params = LNbits.utils.prepareFilterQuery(this.bidsTable, props);
        const auctionItemId = this.bidForm.data.id;
        const { data } = await LNbits.api.request(
          "GET",
          `/auction_house/api/v1/bids/${auctionItemId}` +
            `/paginated?only_mine=${this.onlyMyBids}` +
            `&include_unpaid=${this.showUnpaidBids}&${params}`,
        );

        this.bidsList = data.data;
        this.bidsTable.pagination.rowsNumber = data.total;
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
      } catch (error) {
        LNbits.utils.notifyApiError(error);
      }
    },
    placeBid: async function () {
      const auctionItemId = this.bidForm.data.id;
      if (!this.bidMemo) {
        this.$q.notify({
          type: "warning",
          message: "Please enter a memo!",
        });
        return;
      }
      try {
        const { data } = await LNbits.api.request(
          "PUT",
          `/auction_house/api/v1/bids/${auctionItemId}`,
          null,
          {
            amount: this.bidPrice,
            ln_address: this.lnAddress,
            memo: this.bidMemo,
          },
        );
        this.bidRequest = data;
        this.showBidRequestQrCode = true;
        this.$q.notify({
          type: "positive",
          message: "Pay the invoice to confirm the bid!",
          caption: "Bid pending.",
        });
        this.waitForPayment(this.bidRequest.payment_hash);
      } catch (error) {
        LNbits.utils.notifyApiError(error);
      }
    },
    async waitForPayment(paymentHash) {
      try {
        const url = new URL(window.location);
        url.protocol = url.protocol === "https:" ? "wss" : "ws";
        url.pathname = `/api/v1/ws/${paymentHash}`;
        const ws = new WebSocket(url);
        ws.addEventListener("message", async ({ data }) => {
          const payment = JSON.parse(data);
          if (payment.pending === false) {
            Quasar.Notify.create({
              type: "positive",
              message: "Invoice Paid!",
            });
            this.showBidRequestQrCode = false;
            ws.close();
            setTimeout(() => {
              window.location.reload();
            }, 2000);
          }
        });
      } catch (err) {
        console.warn(err);
        LNbits.utils.notifyApiError(err);
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
    initTimeLeft: function (item) {
      setInterval(() => {
        item.time_left_seconds -= 1;
        const duration = moment.utc(item.time_left_seconds * 1000);
        this.timeLeft = {
          days: +duration.format("DDD") - 1,
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
