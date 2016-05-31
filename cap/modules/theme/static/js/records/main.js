require([
    'js/records/app',
  ], function(app) {
      // Initialize the app
      angular.element(document).ready(function() {
        angular.bootstrap(document.getElementById("cap-records"), ['cap.records']);
        angular.bootstrap(document.getElementById("record-display"), ['cap.records']);
      });

      // Emit info
      console.info('Hello from CERN Analysis Preservation records');
});
