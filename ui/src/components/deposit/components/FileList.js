import React from 'react';

import {
  Box,
  Button,
  Label,
  Menu,
  Anchor,
  List,
  ListItem
} from 'grommet';

import ListPlaceholder from 'grommet-addons/components/ListPlaceholder';
import AddIcon from 'grommet/components/icons/base/Add';
import Status from 'grommet/components/icons/Status';

import FileItem from './FileItem';

import ArchiveIcon from 'grommet/components/icons/base/Archive';
import DocumentConfigIcon from 'grommet/components/icons/base/DocumentConfig';
import PieChartIcon from 'grommet/components/icons/base/PieChart';
import BookIcon from 'grommet/components/icons/base/Book';
import NoteIcon from 'grommet/components/icons/base/Note';
import MoreIcon from 'grommet/components/icons/base/More';

import prettyBytes from 'pretty-bytes';

import {connect} from 'react-redux';

const uploadStatusMap = {
  "uploading": "disabled",
  "error": "critical",
  "done": "ok"
};

class FileList extends React.Component {
  constructor(props) {
    super(props);
  }

  _getIcon(type) {
    const catToIcon = {
      default: <ArchiveIcon type="status" size="xsmall"/>,
      archive: <ArchiveIcon type="status" size="xsmall"/>,
      configuration: <DocumentConfigIcon type="status" size="xsmall"/>,
      dataset: <PieChartIcon type="status" size="xsmall"/>,
      publication: <BookIcon type="status" size="xsmall"/>,
      plot: <PieChartIcon type="status" size="xsmall"/>,
    };

    return catToIcon[type] ? catToIcon[type] : <NoteIcon type="status" size="xsmall" />;
  }

  _actionItem(selected) {
    this.props.action(selected);
  }

  render() {
    return (
      <List selectable={this.props.selectableActionLayer ? true : false}>
        {
          this.props.files && this.props.files.size > 0 ?
          this.props.files.keySeq().toArray().map((filename) => {
            let file = this.props.files.get(filename)
            return <FileItem action={key => this._actionItem.bind(this, key)} file={file} />;
          }) :
          <ListPlaceholder
            emptyMessage="No files have been attached to this project."
            unfilteredTotal={0}/>
        }
      </List>
    );
  }
}


function mapStateToProps(state) {
  return {
    selectableActionLayer: state.drafts.get("fileManagerLayerSelectableAction")
  };
}

function mapDispatchToProps(dispatch) {
  return {
    toggleFilemanagerLayer: () => dispatch(toggleFilemanagerLayer())
  };
}

export default connect(
  mapStateToProps,
  mapDispatchToProps
)(FileList);
