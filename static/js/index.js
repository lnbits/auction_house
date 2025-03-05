const mapAuctionHouse = function (obj) {
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
      auction_houses: [],
      addresses: [],
      biddingType: [
        { value: "auction", label: "Auction" },
        { value: "fixed_price", label: "Fixed Price" },
      ],
      auction_houseRankingBraketOptions: [
        200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000, 200000, 500000,
        1000000,
      ],
      currencyOptions: [],
      auction_housesTable: {
        columns: [
          { name: "id", align: "left", label: "ID", field: "id" },
          {
            name: "auction_house",
            align: "left",
            label: "Name",
            field: "auction_house",
          },
          {
            name: "currency",
            align: "left",
            label: "Currency",
            field: "currency",
          },
          { name: "cost", align: "left", label: "Amount", field: "cost" },
          { name: "time", align: "left", label: "Created At", field: "time" },
        ],
        pagination: {
          rowsPerPage: 10,
        },
      },
      addressesTable: {
        columns: [
          { name: "id", align: "left", label: "ID", field: "id" },
          {
            name: "active",
            align: "left",
            label: "Active",
            field: "active",
            sortable: true,
          },
          {
            name: "local_part",
            align: "left",
            label: "Address",
            field: "local_part",
            sortable: true,
          },
          {
            name: "pubkey",
            align: "left",
            label: "Pubkey",
            field: "pubkey",
            sortable: true,
          },
          {
            name: "reimburse_amount",
            align: "left",
            label: "Reimburse",
            field: "reimburse_amount",
            sortable: true,
          },
          {
            name: "time",
            align: "left",
            label: "Created At",
            field: "time",
            sortable: true,
          },
        ],
        pagination: {
          rowsPerPage: 10,
          page: 1,
          rowsNumber: 10,
        },
      },
      formDialog: {
        show: false,
        data: {},
      },
      auction_houseTab: null,
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
      this.auction_houseTab = "charCount";
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
    getAuctionHouses: function () {
      var self = this;

      LNbits.api
        .request(
          "GET",
          "/bids/api/v1/auction_houses?all_wallets=true",
          this.g.user.wallets[0].inkey,
        )
        .then(function (response) {
          self.auction_houses = response.data.map(function (obj) {
            return mapAuctionHouse(obj);
          });
        });
    },

    getAddresses: function (props) {
      var self = this;
      if (props) {
        self.addressesTable.pagination = props.pagination;
      }
      let pagination = self.addressesTable.pagination;
      const query = {
        all_wallets: true,
        limit: pagination.rowsPerPage,
        offset: (pagination.page - 1) * pagination.rowsPerPage ?? 0,
        sortby: pagination.sortBy || "time",
        direction: pagination.descending ? "desc" : "asc",
      };
      const params = new URLSearchParams(query);

      LNbits.api
        .request(
          "GET",
          `/bids/api/v1/addresses/paginated?${params}`,
          this.g.user.wallets[0].inkey,
        )
        .then(function (response) {
          const { data, total } = response.data;
          self.addressesTable.pagination.rowsNumber = total;
          self.addresses = data.map(function (obj) {
            return mapAuctionHouse(obj);
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
    saveAuctionHouse: function () {
      var data = this.formDialog.data;
      var self = this;
      const method = this.formDialog.data.id ? "PUT" : "POST";

      LNbits.api
        .request(
          method,
          "/bids/api/v1/auction_house",
          _.findWhere(this.g.user.wallets, { id: this.formDialog.data.wallet })
            .adminkey,
          data,
        )
        .then(function (response) {
          self.auction_houses = self.auction_houses.filter(
            (d) => d.id !== response.data.id,
          );
          self.auction_houses.push(mapAuctionHouse(response.data));
          self.resetFormDialog();
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error);
        });
    },

    deleteAuctionHouse: function (auction_house_id) {
      var self = this;
      var auction_house = _.findWhere(this.auction_houses, {
        id: auction_house_id,
      });

      LNbits.utils
        .confirmDialog("Are you sure you want to delete this auction house?")
        .onOk(function () {
          LNbits.api
            .request(
              "DELETE",
              "/bids/api/v1/auction_house/" + auction_house_id,
              _.findWhere(self.g.user.wallets, { id: auction_house.wallet })
                .adminkey,
            )
            .then(function (response) {
              self.auction_houses = self.auction_houses.filter(
                (d) => d.id !== auction_house_id,
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
      var auction_house = _.findWhere(this.auction_houses, {
        id: formDialog.data.auction_house_id,
      });
      var adminkey = _.findWhere(self.g.user.wallets, {
        id: auction_house.wallet,
      }).adminkey;

      LNbits.api
        .request(
          "POST",
          "/bids/api/v1/auction_house/" +
            formDialog.data.auction_house_id +
            "/address",
          adminkey,
          formDialog.data,
        )
        .then(function (response) {
          self.resetFormDialog();
          self.getAddresses();
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error);
        });
    },
    updateAddress: function () {
      var self = this;
      var data = this.addressFormDialog.data;
      var auction_house = _.findWhere(this.auction_houses, {
        id: data.auction_house_id,
      });
      return LNbits.api
        .request(
          "PUT",
          "/bids/api/v1/auction_house/" +
            data.auction_house_id +
            "/address/" +
            data.id,
          _.findWhere(self.g.user.wallets, { id: auction_house.wallet })
            .adminkey,
          {
            pubkey: data.pubkey,
            relays: data.config.relays,
          },
        )
        .then(function (response) {
          self.resetFormDialog();
          self.getAddresses();
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error);
        });
    },
    deleteAddress: function (address_id) {
      var self = this;
      var address = _.findWhere(this.addresses, { id: address_id });
      var auction_house = _.findWhere(this.auction_houses, {
        id: address.auction_house_id,
      });

      LNbits.utils
        .confirmDialog("Are you sure you want to delete this address?")
        .onOk(function () {
          LNbits.api
            .request(
              "DELETE",
              `/bids/api/v1/auction_house/${auction_house.id}/address/${address_id}`,
              _.findWhere(self.g.user.wallets, { id: auction_house.wallet })
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
    activateAddress: function (auction_house_id, address_id) {
      var self = this;
      var address = _.findWhere(this.addresses, { id: address_id });
      var auction_house = _.findWhere(this.auction_houses, {
        id: address.auction_house_id,
      });
      LNbits.utils
        .confirmDialog(
          "Are you sure you want to manually activate this address?",
        )
        .onOk(function () {
          return LNbits.api
            .request(
              "PUT",
              "/bids/api/v1/auction_house/" +
                auction_house_id +
                "/address/" +
                address_id +
                "/activate",
              _.findWhere(self.g.user.wallets, { id: auction_house.wallet })
                .adminkey,
            )
            .then(function (response) {
              if (response.data.success) {
                self.$q.notify({
                  type: "positive",
                  message: "Address activated",
                });
              }
              self.getAddresses();
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
          `/bids/api/v1/auction_house/${address.auction_house_id}` +
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
    refreshAuctionHouseRanking: function (braket) {
      var self = this;
      return LNbits.api
        .request(
          "PUT",
          "/bids/api/v1/auction_house/ranking/" + braket,
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
    addAuctionHouseRanking: function () {
      var self = this;
      return LNbits.api
        .request(
          "PATCH",
          "/bids/api/v1/auction_house/ranking/" +
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
    searchIdentifier: function () {
      var self = this;
      return LNbits.api
        .request(
          "GET",
          "/bids/api/v1/ranking/search?q=" +
            this.identifierFormDialog.data.searchText,
          self.g.user.wallets[0].adminkey,
        )
        .then(function (response) {
          self.identifierFormDialog.data.identifier = response.data;
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error);
        });
    },
    updateIdentifier: function () {
      var self = this;
      return LNbits.api
        .request(
          "PUT",
          "/bids/api/v1/ranking",
          self.g.user.wallets[0].adminkey,
          {
            name: self.identifierFormDialog.data.identifier.name,
            rank: self.identifierFormDialog.data.identifier.rank,
          },
        )
        .then(function (response) {
          self.$q.notify({
            type: "positive",
            message: "Identifier updated!",
          });
          self.resetFormDialog();
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error);
        });
    },

    fetchSettings: function () {
      var self = this;
      return LNbits.api
        .request(
          "GET",
          "/bids/api/v1/settings",
          self.g.user.wallets[0].adminkey,
        )
        .then(function (response) {
          self.settingsFormDialog.data = response.data;
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error);
        });
    },
    updateSettings: function () {
      var self = this;
      return LNbits.api
        .request(
          "PUT",
          "/bids/api/v1/settings",
          self.g.user.wallets[0].adminkey,
          self.settingsFormDialog.data,
        )
        .then(function (response) {
          self.resetFormDialog();
          self.$q.notify({
            type: "positive",
            message: "Updated settings",
          });
        })
        .catch(function (error) {
          LNbits.utils.notifyApiError(error);
        });
    },

    auction_houseNameFromId: function (auction_houseId) {
      const auction_house =
        this.auction_houses.find((d) => d.id === auction_houseId) || {};
      return auction_house.auction_house || "";
    },
    addressFullName: function (address) {
      if (!address) {
        return "";
      }
      const auction_house = this.auction_houseNameFromId(
        address.auction_house_id,
      );
      return `${address.local_part}@${auction_house}`;
    },
    exportCSV: function () {
      LNbits.utils.exportCSV(
        this.auction_housesTable.columns,
        this.auction_houses,
      );
    },
    exportAddressesCSV: function () {
      LNbits.utils.exportCSV(this.addressesTable.columns, this.addresses);
    },
  },
  created() {
    this.resetFormDialog();
    if (this.g.user.wallets.length) {
      this.getAuctionHouses();
      this.getAddresses();
      this.fetchSettings();
    }
    LNbits.api
      .request("GET", "/api/v1/currencies")
      .then((response) => {
        this.currencyOptions = ["sats", ...response.data];
      })
      .catch(LNbits.utils.notifyApiError);
  },
  computed: {
    auction_houseOptions: function () {
      return this.auction_houses.map((el) => {
        return {
          label: el.auction_house,
          value: el.id,
        };
      });
    },
    auction_houseRankingAllOptions: function () {
      const rankings = this.auction_houseRankingBraketOptions.map((r) => ({
        value: r,
        label: `Top ${r} identifiers`,
      }));
      return [{ value: 0, label: "Reserved" }].concat(rankings);
    },
  },
});
