window.app = Vue.createApp({
  el: "#vue",
  mixins: [window.windowMixin],
  data: function () {
    return {
      currencyOptions: [],
      auctionRoomForm: {
        show: false,
        data: auction_room,
      },
      auctionRoomTab: "overview",
      webhookTab: "lockTab",
    };
  },
  methods: {
    saveAuctionRoom: async function () {
      try {
        await LNbits.api.request(
          "PUT",
          "/auction_house/api/v1/auction_room",
          null,
          this.auctionRoomForm.data,
        );
        this.$q.notify({
          type: "positive",
          message: "Auction Room updated!",
        });
      } catch (error) {
        this.$q.notify({
          type: "negative",
          message: "Failed to update!",
        });
        LNbits.utils.notifyApiError(error);
      }
    },
    prefillWebhooks: function () {
      this.auctionRoomForm.data.extra.lock_webhook.method = "PUT";
      this.auctionRoomForm.data.extra.lock_webhook.url =
        "http://localhost:5000/nostrnip5/api/v1/domain/XXXXXXXXXX/address/lock";
      this.auctionRoomForm.data.extra.lock_webhook.data = `{\n "transfer_code": "\${transfer_code}"\n}`;
      this.auctionRoomForm.data.extra.unlock_webhook.method = "PUT";
      this.auctionRoomForm.data.extra.unlock_webhook.url =
        "http://localhost:5000/nostrnip5/api/v1/domain/XXXXXXXXXX/address/unlock";
      this.auctionRoomForm.data.extra.unlock_webhook.data = `{\n "lock_code": "\${lock_code}"\n}`;

      this.auctionRoomForm.data.extra.transfer_webhook.method = "PUT";
      this.auctionRoomForm.data.extra.transfer_webhook.url =
        "http://localhost:5000/nostrnip5/api/v1/domain/XXXXXXXXXX/address/transfer";
      this.auctionRoomForm.data.extra.transfer_webhook.data = `{\n "lock_code": "\${lock_code}",\n "new_owner_id": "\${new_owner_id}"\n}`;
    },
  },
  created() {
    LNbits.api
      .request("GET", "/api/v1/currencies")
      .then((response) => {
        this.currencyOptions = ["sat", ...response.data];
      })
      .catch(LNbits.utils.notifyApiError);
  },
});
