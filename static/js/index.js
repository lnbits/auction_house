const mapAuctionRoom = function (obj) {
  obj.time = Quasar.date.formatDate(
    new Date(obj.time * 1000),
    "YYYY-MM-DD HH:mm",
  );

  return obj;
};

window.app = Vue.createApp({
  el: "#vue",
  mixins: [window.windowMixin],
  data: function () {
    return {
      auction_rooms: [],
      addresses: [],
      biddingType: [
        { value: "auction", label: "Auction" },
        { value: "fixed_price", label: "Fixed Price" },
      ],
      auction_roomRankingBraketOptions: [
        200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000,
        1000000,
      ],
      currencyOptions: [],
      auction_roomsTable: {
        columns: [
          {
            name: "created_at",
            align: "left",
            label: "Created At",
            field: "created_at",
            format: (val) => LNbits.utils.formatDateString(val),
          },

          {
            name: "name",
            align: "left",
            label: "Name",
            field: "name",
          },
          {
            name: "currency",
            align: "left",
            label: "Currency",
            field: "currency",
          },
          { name: "type", align: "left", label: "Type", field: "type" },
          { name: "days", align: "left", label: "Days", field: "days" },
          {
            name: "room_percentage",
            align: "left",
            label: "Room %",
            field: "room_percentage",
          },
          {
            name: "min_bid_up_percentage",
            align: "left",
            label: "Min Bid %",
            field: "min_bid_up_percentage",
          },
          { name: "id", align: "left", label: "Room Id", field: "id" },
        ],
        pagination: {
          rowsPerPage: 10,
        },
      },

      formDialog: {
        show: false,
        data: {},
      },
      auctionRoomTab: null,
      addressFormDialog: {
        show: false,
        data: {},
      },
      rankingFormDialog: {
        show: false,
        data: {},
      },
      identifierFormDialog: {
        show: false,
        data: {},
      },
      settingsFormDialog: {
        show: false,
        data: {},
      },
      qrCodeDialog: {
        show: false,
        data: {},
      },
    };
  },
  methods: {
    resetFormDialog: function () {
      this.formDialog.show = false;
      this.auctionRoomTab = "webhooks";
      this.formDialog.data = {
        cost_extra: {
          max_years: 1,
          char_count_cost: [],
          rank_cost: [],
        },
      };
      this.addressFormDialog.show = false;
      this.addressFormDialog.data = {
        relay: "",
        config: {
          relays: [],
        },
        pubkey: "",
        local_part: "",
      };
      this.rankingFormDialog.show = false;
      this.rankingFormDialog.data = {
        bucket: 0,
        identifiers: "",
      };
      this.identifierFormDialog.show = false;
      this.identifierFormDialog.data = {
        searchText: "",
        bucket: 0,
        identifier: "",
      };
      this.settingsFormDialog.show = false;
      this.qrCodeDialog.show = false;
      this.qrCodeDialog.data = {
        payment_request: "",
      };
    },
    closeAddressFormDialog: function () {
      this.resetFormDialog();
    },
    closeFormDialog: function () {
      this.resetFormDialog();
    },
    getAuctionRooms: function () {
      var self = this;

      LNbits.api
        .request(
          "GET",
          "/auction_house/api/v1/auction_rooms",
          this.g.user.wallets[0].inkey,
        )
        .then(function (response) {
          self.auction_rooms = response.data.map(function (obj) {
            return mapAuctionRoom(obj);
          });
        });
    },

    editAddress: function (address) {
      this.addressFormDialog.show = true;
      this.addressFormDialog.data = address;
    },
    addRelayForAddress: function (event) {
      event.preventDefault();
      this.removeRelayForAddress(this.addressFormDialog.data.relay);
      if (this.addressFormDialog.data.relay) {
        this.addressFormDialog.data.config.relays.push(
          this.addressFormDialog.data.relay,
        );
      }
      this.addressFormDialog.data.relay = "";
    },
    removeRelayForAddress: function (relay) {
      this.addressFormDialog.data.config.relays = (
        this.addressFormDialog.data.config.relays || []
      ).filter((r) => r !== relay);
    },
    saveAuctionRoom: function () {
      var data = this.formDialog.data;
      var self = this;
      const method = this.formDialog.data.id ? "PUT" : "POST";

      LNbits.api
        .request(
          method,
          "/auction_house/api/v1/auction_room",
          _.findWhere(this.g.user.wallets, { id: this.formDialog.data.wallet })
            .adminkey,
          data,
        )
        .then(function (response) {
          self.auction_rooms = self.auction_rooms.filter(
            (d) => d.id !== response.data.id,
          );
          self.auction_rooms.push(mapAuctionRoom(response.data));
          self.resetFormDialog();
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error);
        });
    },

    deleteAuctionRoom: function (auction_room_id) {
      var self = this;
      var auction_room = _.findWhere(this.auction_rooms, {
        id: auction_room_id,
      });

      LNbits.utils
        .confirmDialog("Are you sure you want to delete this auction room?")
        .onOk(function () {
          LNbits.api
            .request(
              "DELETE",
              "/auction_house/api/v1/auction_room/" + auction_room_id,
              _.findWhere(self.g.user.wallets, { id: auction_room.wallet })
                .adminkey,
            )
            .then(function (response) {
              self.auction_rooms = self.auction_rooms.filter(
                (d) => d.id !== auction_room_id,
              );
            })
            .catch(function (error) {
              LNbits.utils.notifyApiError(error);
            });
        });
    },
    saveAddress: function () {
      var self = this;
      var formDialog = this.addressFormDialog;
      if (formDialog.data.id) {
        this.updateAddress();
        return;
      }
      var auction_room = _.findWhere(this.auction_rooms, {
        id: formDialog.data.auction_room_id,
      });
      var adminkey = _.findWhere(self.g.user.wallets, {
        id: auction_room.wallet,
      }).adminkey;

      LNbits.api
        .request(
          "POST",
          "/auction_house/api/v1/auction_room/" +
            formDialog.data.auction_room_id +
            "/address",
          adminkey,
          formDialog.data,
        )
        .then(function (response) {
          self.resetFormDialog();
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error);
        });
    },
    updateAddress: function () {
      var self = this;
      var data = this.addressFormDialog.data;
      var auction_room = _.findWhere(this.auction_rooms, {
        id: data.auction_room_id,
      });
      return LNbits.api
        .request(
          "PUT",
          "/auction_house/api/v1/auction_room/" +
            data.auction_room_id +
            "/address/" +
            data.id,
          _.findWhere(self.g.user.wallets, { id: auction_room.wallet })
            .adminkey,
          {
            pubkey: data.pubkey,
            relays: data.config.relays,
          },
        )
        .then(function (response) {
          self.resetFormDialog();
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error);
        });
    },
    deleteAddress: function (address_id) {
      var self = this;
      var address = _.findWhere(this.addresses, { id: address_id });
      var auction_room = _.findWhere(this.auction_rooms, {
        id: address.auction_room_id,
      });

      LNbits.utils
        .confirmDialog("Are you sure you want to delete this address?")
        .onOk(function () {
          LNbits.api
            .request(
              "DELETE",
              `/auction_house/api/v1/auction_room/${auction_room.id}/address/${address_id}`,
              _.findWhere(self.g.user.wallets, { id: auction_room.wallet })
                .adminkey,
            )
            .then(function (response) {
              self.addresses = _.reject(self.addresses, function (obj) {
                return obj.id == address_id;
              });
            })
            .catch(function (error) {
              LNbits.utils.notifyApiError(error);
            });
        });
    },
    activateAddress: function (auction_room_id, address_id) {
      var self = this;
      var address = _.findWhere(this.addresses, { id: address_id });
      var auction_room = _.findWhere(this.auction_rooms, {
        id: address.auction_room_id,
      });
      LNbits.utils
        .confirmDialog(
          "Are you sure you want to manually activate this address?",
        )
        .onOk(function () {
          return LNbits.api
            .request(
              "PUT",
              "/auction_house/api/v1/auction_room/" +
                auction_room_id +
                "/address/" +
                address_id +
                "/activate",
              _.findWhere(self.g.user.wallets, { id: auction_room.wallet })
                .adminkey,
            )
            .then(function (response) {
              if (response.data.success) {
                self.$q.notify({
                  type: "positive",
                  message: "AuctionItem activated",
                });
              }
            })
            .catch(function (error) {
              LNbits.utils.notifyApiError(error);
            });
        });
    },
    showReimburseInvoice: function (address) {
      if (!address || address.reimburse_amount <= 0) {
        this.$q.notify({
          type: "warning",
          message: "Nothing to reimburse.",
        });
        return;
      }
      var self = this;
      self.$q.notify({
        type: "positive",
        message: "Generating reimbursement invoice.",
      });
      return LNbits.api
        .request(
          "GET",
          `/auction_house/api/v1/auction_room/${address.auction_room_id}` +
            `/address/${address.id}/reimburse`,
          self.g.user.wallets[0].adminkey,
        )
        .then(function (response) {
          self.qrCodeDialog.show = true;
          self.qrCodeDialog.data = response.data;
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error);
        });
    },
    refreshAuctionRoomRanking: function (braket) {
      var self = this;
      return LNbits.api
        .request(
          "PUT",
          "/auction_house/api/v1/auction_room/ranking/" + braket,
          self.g.user.wallets[0].adminkey,
        )
        .then(function (response) {
          self.$q.notify({
            type: "positive",
            message: `Top ${braket} identifiers refreshed!`,
          });
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error);
        });
    },
    addAuctionRoomRanking: function () {
      var self = this;
      return LNbits.api
        .request(
          "PATCH",
          "/auction_house/api/v1/auction_room/ranking/" +
            this.rankingFormDialog.data.bucket,
          self.g.user.wallets[0].adminkey,
          this.rankingFormDialog.data.identifiers,
        )
        .then(function (response) {
          self.$q.notify({
            type: "positive",
            message: "Identifiers updated!",
          });
          self.resetFormDialog();
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error);
        });
    },

    auction_roomNameFromId: function (auction_roomId) {
      const auction_room =
        this.auction_rooms.find((d) => d.id === auction_roomId) || {};
      return auction_room.auction_room || "";
    },
    addressFullName: function (address) {
      if (!address) {
        return "";
      }
      const auction_room = this.auction_roomNameFromId(address.auction_room_id);
      return `${address.local_part}@${auction_room}`;
    },
    exportCSV: function () {
      LNbits.utils.exportCSV(
        this.auction_roomsTable.columns,
        this.auction_rooms,
      );
    },
    exportAddressesCSV: function () {
      LNbits.utils.exportCSV(this.addressesTable.columns, this.addresses);
    },
  },
  created() {
    this.resetFormDialog();
    if (this.g.user.wallets.length) {
      this.getAuctionRooms();
    }
    LNbits.api
      .request("GET", "/api/v1/currencies")
      .then((response) => {
        this.currencyOptions = ["sat", ...response.data];
      })
      .catch(LNbits.utils.notifyApiError);
  },
  computed: {
    auctionRoomOptions: function () {
      return this.auction_rooms.map((el) => {
        return {
          label: el.auction_room,
          value: el.id,
        };
      });
    },
    auction_roomRankingAllOptions: function () {
      const rankings = this.auction_roomRankingBraketOptions.map((r) => ({
        value: r,
        label: `Top ${r} identifiers`,
      }));
      return [{ value: 0, label: "Reserved" }].concat(rankings);
    },
  },
});
