namespace LGClientDisplayNew
{
    partial class Form1
    {
        /// <summary>
        /// 필수 디자이너 변수입니다.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// 사용 중인 모든 리소스를 정리합니다.
        /// </summary>
        /// <param name="disposing">관리되는 리소스를 삭제해야 하면 true이고, 그렇지 않으면 false입니다.</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows Form 디자이너에서 생성한 코드

        /// <summary>
        /// 디자이너 지원에 필요한 메서드입니다. 
        /// 이 메서드의 내용을 코드 편집기로 수정하지 마세요.
        /// </summary>
        private void InitializeComponent()
        {
            this.components = new System.ComponentModel.Container();
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(Form1));
            this.BtnConn = new System.Windows.Forms.Button();
            this.BtnDiscon = new System.Windows.Forms.Button();
            this.PictureBoxRcsVideo = new System.Windows.Forms.PictureBox();
            this.LblRcsIpAddr = new System.Windows.Forms.Label();
            this.TmrHeartBeatRequest = new System.Windows.Forms.Timer(this.components);
            this.TxtRcsIpAddr = new System.Windows.Forms.TextBox();
            this.TxtRcsPasswd = new System.Windows.Forms.TextBox();
            this.LblRcsPrearmedPasswd = new System.Windows.Forms.Label();
            this.TxtCurrentRcsState = new System.Windows.Forms.TextBox();
            this.LblCurrentRcsState = new System.Windows.Forms.Label();
            this.GbxRcsControl = new System.Windows.Forms.GroupBox();
            this.BtnPreArmedSetup = new System.Windows.Forms.Button();
            this.GbxRcsEngageCalControl = new System.Windows.Forms.GroupBox();
            this.BtnFireCancel = new System.Windows.Forms.Button();
            this.BtnDownDecY = new System.Windows.Forms.Button();
            this.BtnRightIncX = new System.Windows.Forms.Button();
            this.BtnUpIncY = new System.Windows.Forms.Button();
            this.BtnFire = new System.Windows.Forms.Button();
            this.BtnLeftDecX = new System.Windows.Forms.Button();
            this.TxtAutoEngageList = new System.Windows.Forms.TextBox();
            this.LblAutoEngageList = new System.Windows.Forms.Label();
            this.LblRcsEngageCalControl = new System.Windows.Forms.Label();
            this.CmbModeSelect = new System.Windows.Forms.ComboBox();
            this.TxtRcsTcpPort = new System.Windows.Forms.TextBox();
            this.LblTcpPort = new System.Windows.Forms.Label();
            ((System.ComponentModel.ISupportInitialize)(this.PictureBoxRcsVideo)).BeginInit();
            this.GbxRcsControl.SuspendLayout();
            this.GbxRcsEngageCalControl.SuspendLayout();
            this.SuspendLayout();
            // 
            // BtnConn
            // 
            this.BtnConn.Font = new System.Drawing.Font("Arial", 9F);
            this.BtnConn.Location = new System.Drawing.Point(40, 24);
            this.BtnConn.Name = "BtnConn";
            this.BtnConn.Size = new System.Drawing.Size(101, 46);
            this.BtnConn.TabIndex = 0;
            this.BtnConn.Text = "Connect";
            this.BtnConn.UseVisualStyleBackColor = true;
            this.BtnConn.Click += new System.EventHandler(this.ConnBtn_Click);
            // 
            // BtnDiscon
            // 
            this.BtnDiscon.Font = new System.Drawing.Font("Arial", 9F);
            this.BtnDiscon.Location = new System.Drawing.Point(147, 24);
            this.BtnDiscon.Name = "BtnDiscon";
            this.BtnDiscon.Size = new System.Drawing.Size(101, 46);
            this.BtnDiscon.TabIndex = 1;
            this.BtnDiscon.Text = "Discon";
            this.BtnDiscon.UseVisualStyleBackColor = true;
            this.BtnDiscon.Click += new System.EventHandler(this.DisconBtn_Click);
            // 
            // PictureBoxRcsVideo
            // 
            this.PictureBoxRcsVideo.ErrorImage = ((System.Drawing.Image)(resources.GetObject("PictureBoxRcsVideo.ErrorImage")));
            this.PictureBoxRcsVideo.InitialImage = ((System.Drawing.Image)(resources.GetObject("PictureBoxRcsVideo.InitialImage")));
            this.PictureBoxRcsVideo.Location = new System.Drawing.Point(273, 97);
            this.PictureBoxRcsVideo.Name = "PictureBoxRcsVideo";
            this.PictureBoxRcsVideo.Size = new System.Drawing.Size(796, 601);
            this.PictureBoxRcsVideo.SizeMode = System.Windows.Forms.PictureBoxSizeMode.StretchImage;
            this.PictureBoxRcsVideo.TabIndex = 2;
            this.PictureBoxRcsVideo.TabStop = false;
            // 
            // LblRcsIpAddr
            // 
            this.LblRcsIpAddr.AutoSize = true;
            this.LblRcsIpAddr.Font = new System.Drawing.Font("Arial", 9F);
            this.LblRcsIpAddr.Location = new System.Drawing.Point(273, 38);
            this.LblRcsIpAddr.Name = "LblRcsIpAddr";
            this.LblRcsIpAddr.Size = new System.Drawing.Size(95, 21);
            this.LblRcsIpAddr.TabIndex = 5;
            this.LblRcsIpAddr.Text = "IP Address";
            // 
            // TmrHeartBeatRequest
            // 
            this.TmrHeartBeatRequest.Tick += new System.EventHandler(this.TmrHeartBeatRequest_Tick);
            // 
            // TxtRcsIpAddr
            // 
            this.TxtRcsIpAddr.Location = new System.Drawing.Point(374, 33);
            this.TxtRcsIpAddr.Name = "TxtRcsIpAddr";
            this.TxtRcsIpAddr.Size = new System.Drawing.Size(161, 28);
            this.TxtRcsIpAddr.TabIndex = 6;
            // 
            // TxtRcsPasswd
            // 
            this.TxtRcsPasswd.Location = new System.Drawing.Point(20, 114);
            this.TxtRcsPasswd.Name = "TxtRcsPasswd";
            this.TxtRcsPasswd.Size = new System.Drawing.Size(197, 26);
            this.TxtRcsPasswd.TabIndex = 5;
            // 
            // LblRcsPrearmedPasswd
            // 
            this.LblRcsPrearmedPasswd.AutoSize = true;
            this.LblRcsPrearmedPasswd.Location = new System.Drawing.Point(20, 90);
            this.LblRcsPrearmedPasswd.Name = "LblRcsPrearmedPasswd";
            this.LblRcsPrearmedPasswd.Size = new System.Drawing.Size(127, 19);
            this.LblRcsPrearmedPasswd.TabIndex = 6;
            this.LblRcsPrearmedPasswd.Text = "RCS Passwords";
            // 
            // TxtCurrentRcsState
            // 
            this.TxtCurrentRcsState.Location = new System.Drawing.Point(20, 52);
            this.TxtCurrentRcsState.Name = "TxtCurrentRcsState";
            this.TxtCurrentRcsState.Size = new System.Drawing.Size(197, 26);
            this.TxtCurrentRcsState.TabIndex = 7;
            // 
            // LblCurrentRcsState
            // 
            this.LblCurrentRcsState.AutoSize = true;
            this.LblCurrentRcsState.Location = new System.Drawing.Point(20, 29);
            this.LblCurrentRcsState.Name = "LblCurrentRcsState";
            this.LblCurrentRcsState.Size = new System.Drawing.Size(145, 19);
            this.LblCurrentRcsState.TabIndex = 8;
            this.LblCurrentRcsState.Text = "RCS Current State";
            // 
            // GbxRcsControl
            // 
            this.GbxRcsControl.Controls.Add(this.BtnPreArmedSetup);
            this.GbxRcsControl.Controls.Add(this.LblCurrentRcsState);
            this.GbxRcsControl.Controls.Add(this.TxtCurrentRcsState);
            this.GbxRcsControl.Controls.Add(this.LblRcsPrearmedPasswd);
            this.GbxRcsControl.Controls.Add(this.TxtRcsPasswd);
            this.GbxRcsControl.Font = new System.Drawing.Font("Arial", 8.25F);
            this.GbxRcsControl.Location = new System.Drawing.Point(33, 86);
            this.GbxRcsControl.Name = "GbxRcsControl";
            this.GbxRcsControl.Size = new System.Drawing.Size(234, 195);
            this.GbxRcsControl.TabIndex = 4;
            this.GbxRcsControl.TabStop = false;
            this.GbxRcsControl.Text = "RCS Pre-armed Setup";
            // 
            // BtnPreArmedSetup
            // 
            this.BtnPreArmedSetup.Location = new System.Drawing.Point(20, 150);
            this.BtnPreArmedSetup.Name = "BtnPreArmedSetup";
            this.BtnPreArmedSetup.Size = new System.Drawing.Size(197, 37);
            this.BtnPreArmedSetup.TabIndex = 14;
            this.BtnPreArmedSetup.Text = "Pre-armed Setup";
            this.BtnPreArmedSetup.UseVisualStyleBackColor = true;
            this.BtnPreArmedSetup.Click += new System.EventHandler(this.BtnPreArmedSetup_Click);
            // 
            // GbxRcsEngageCalControl
            // 
            this.GbxRcsEngageCalControl.Controls.Add(this.BtnFireCancel);
            this.GbxRcsEngageCalControl.Controls.Add(this.BtnDownDecY);
            this.GbxRcsEngageCalControl.Controls.Add(this.BtnRightIncX);
            this.GbxRcsEngageCalControl.Controls.Add(this.BtnUpIncY);
            this.GbxRcsEngageCalControl.Controls.Add(this.BtnFire);
            this.GbxRcsEngageCalControl.Controls.Add(this.BtnLeftDecX);
            this.GbxRcsEngageCalControl.Controls.Add(this.TxtAutoEngageList);
            this.GbxRcsEngageCalControl.Controls.Add(this.LblAutoEngageList);
            this.GbxRcsEngageCalControl.Controls.Add(this.LblRcsEngageCalControl);
            this.GbxRcsEngageCalControl.Controls.Add(this.CmbModeSelect);
            this.GbxRcsEngageCalControl.Font = new System.Drawing.Font("Arial", 8.25F);
            this.GbxRcsEngageCalControl.Location = new System.Drawing.Point(33, 293);
            this.GbxRcsEngageCalControl.Name = "GbxRcsEngageCalControl";
            this.GbxRcsEngageCalControl.Size = new System.Drawing.Size(234, 405);
            this.GbxRcsEngageCalControl.TabIndex = 7;
            this.GbxRcsEngageCalControl.TabStop = false;
            this.GbxRcsEngageCalControl.Text = "RCS Engage/Cal Control";
            // 
            // BtnFireCancel
            // 
            this.BtnFireCancel.Font = new System.Drawing.Font("Arial", 8.25F);
            this.BtnFireCancel.Location = new System.Drawing.Point(19, 353);
            this.BtnFireCancel.Name = "BtnFireCancel";
            this.BtnFireCancel.Size = new System.Drawing.Size(196, 38);
            this.BtnFireCancel.TabIndex = 24;
            this.BtnFireCancel.Text = "Fire Cancel";
            this.BtnFireCancel.UseVisualStyleBackColor = true;
            // 
            // BtnDownDecY
            // 
            this.BtnDownDecY.Font = new System.Drawing.Font("Arial", 6F);
            this.BtnDownDecY.Location = new System.Drawing.Point(89, 291);
            this.BtnDownDecY.Name = "BtnDownDecY";
            this.BtnDownDecY.Size = new System.Drawing.Size(50, 50);
            this.BtnDownDecY.TabIndex = 21;
            this.BtnDownDecY.Text = "Down\r\n(K)";
            this.BtnDownDecY.UseVisualStyleBackColor = true;
            // 
            // BtnRightIncX
            // 
            this.BtnRightIncX.Font = new System.Drawing.Font("Arial", 6F);
            this.BtnRightIncX.Location = new System.Drawing.Point(159, 235);
            this.BtnRightIncX.Name = "BtnRightIncX";
            this.BtnRightIncX.Size = new System.Drawing.Size(50, 50);
            this.BtnRightIncX.TabIndex = 20;
            this.BtnRightIncX.Text = "Right\r\n(L)";
            this.BtnRightIncX.UseVisualStyleBackColor = true;
            // 
            // BtnUpIncY
            // 
            this.BtnUpIncY.Font = new System.Drawing.Font("Arial", 6F);
            this.BtnUpIncY.Location = new System.Drawing.Point(89, 181);
            this.BtnUpIncY.Name = "BtnUpIncY";
            this.BtnUpIncY.Size = new System.Drawing.Size(50, 50);
            this.BtnUpIncY.TabIndex = 23;
            this.BtnUpIncY.Text = "Up\r\n(I)";
            this.BtnUpIncY.UseVisualStyleBackColor = true;
            // 
            // BtnFire
            // 
            this.BtnFire.Font = new System.Drawing.Font("Arial", 6F);
            this.BtnFire.Location = new System.Drawing.Point(89, 235);
            this.BtnFire.Name = "BtnFire";
            this.BtnFire.Size = new System.Drawing.Size(50, 50);
            this.BtnFire.TabIndex = 22;
            this.BtnFire.Text = "Fire\r\n(F)";
            this.BtnFire.UseVisualStyleBackColor = true;
            this.BtnFire.Click += new System.EventHandler(this.BtnFire_Click);
            // 
            // BtnLeftDecX
            // 
            this.BtnLeftDecX.Font = new System.Drawing.Font("Arial", 6F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.BtnLeftDecX.Location = new System.Drawing.Point(25, 235);
            this.BtnLeftDecX.Name = "BtnLeftDecX";
            this.BtnLeftDecX.Size = new System.Drawing.Size(50, 50);
            this.BtnLeftDecX.TabIndex = 19;
            this.BtnLeftDecX.Text = "Left\r\n(J)";
            this.BtnLeftDecX.UseVisualStyleBackColor = true;
            // 
            // TxtAutoEngageList
            // 
            this.TxtAutoEngageList.Location = new System.Drawing.Point(19, 130);
            this.TxtAutoEngageList.Name = "TxtAutoEngageList";
            this.TxtAutoEngageList.Size = new System.Drawing.Size(196, 26);
            this.TxtAutoEngageList.TabIndex = 18;
            // 
            // LblAutoEngageList
            // 
            this.LblAutoEngageList.AutoSize = true;
            this.LblAutoEngageList.Location = new System.Drawing.Point(19, 103);
            this.LblAutoEngageList.Name = "LblAutoEngageList";
            this.LblAutoEngageList.Size = new System.Drawing.Size(133, 19);
            this.LblAutoEngageList.TabIndex = 17;
            this.LblAutoEngageList.Text = "Auto Engage List";
            // 
            // LblRcsEngageCalControl
            // 
            this.LblRcsEngageCalControl.AutoSize = true;
            this.LblRcsEngageCalControl.Font = new System.Drawing.Font("Arial", 8.25F);
            this.LblRcsEngageCalControl.Location = new System.Drawing.Point(23, 32);
            this.LblRcsEngageCalControl.Name = "LblRcsEngageCalControl";
            this.LblRcsEngageCalControl.Size = new System.Drawing.Size(99, 19);
            this.LblRcsEngageCalControl.TabIndex = 15;
            this.LblRcsEngageCalControl.Text = "Mode Select";
            // 
            // CmbModeSelect
            // 
            this.CmbModeSelect.FormattingEnabled = true;
            this.CmbModeSelect.Location = new System.Drawing.Point(19, 60);
            this.CmbModeSelect.Name = "CmbModeSelect";
            this.CmbModeSelect.Size = new System.Drawing.Size(196, 27);
            this.CmbModeSelect.TabIndex = 14;
            this.CmbModeSelect.SelectedIndexChanged += new System.EventHandler(this.CmbModeSelect_SelectedIndexChanged);
            // 
            // TxtRcsTcpPort
            // 
            this.TxtRcsTcpPort.Location = new System.Drawing.Point(664, 32);
            this.TxtRcsTcpPort.Name = "TxtRcsTcpPort";
            this.TxtRcsTcpPort.Size = new System.Drawing.Size(161, 28);
            this.TxtRcsTcpPort.TabIndex = 9;
            // 
            // LblTcpPort
            // 
            this.LblTcpPort.AutoSize = true;
            this.LblTcpPort.Font = new System.Drawing.Font("Arial", 9F);
            this.LblTcpPort.Location = new System.Drawing.Point(570, 37);
            this.LblTcpPort.Name = "LblTcpPort";
            this.LblTcpPort.Size = new System.Drawing.Size(85, 21);
            this.LblTcpPort.TabIndex = 8;
            this.LblTcpPort.Text = "TCP Port";
            // 
            // Form1
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(10F, 18F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(1081, 720);
            this.Controls.Add(this.TxtRcsTcpPort);
            this.Controls.Add(this.LblTcpPort);
            this.Controls.Add(this.GbxRcsEngageCalControl);
            this.Controls.Add(this.TxtRcsIpAddr);
            this.Controls.Add(this.LblRcsIpAddr);
            this.Controls.Add(this.GbxRcsControl);
            this.Controls.Add(this.PictureBoxRcsVideo);
            this.Controls.Add(this.BtnDiscon);
            this.Controls.Add(this.BtnConn);
            this.Name = "Form1";
            this.Text = "LGDisplayNew";
            this.FormClosed += new System.Windows.Forms.FormClosedEventHandler(this.Form1_FormClosed);
            this.Load += new System.EventHandler(this.Form1_Load);
            ((System.ComponentModel.ISupportInitialize)(this.PictureBoxRcsVideo)).EndInit();
            this.GbxRcsControl.ResumeLayout(false);
            this.GbxRcsControl.PerformLayout();
            this.GbxRcsEngageCalControl.ResumeLayout(false);
            this.GbxRcsEngageCalControl.PerformLayout();
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.Button BtnConn;
        private System.Windows.Forms.Button BtnDiscon;
        private System.Windows.Forms.PictureBox PictureBoxRcsVideo;
        private System.Windows.Forms.Label LblRcsIpAddr;
        private System.Windows.Forms.Timer TmrHeartBeatRequest;
        private System.Windows.Forms.TextBox TxtRcsIpAddr;
        private System.Windows.Forms.TextBox TxtRcsPasswd;
        private System.Windows.Forms.Label LblRcsPrearmedPasswd;
        private System.Windows.Forms.TextBox TxtCurrentRcsState;
        private System.Windows.Forms.Label LblCurrentRcsState;
        private System.Windows.Forms.GroupBox GbxRcsControl;
        private System.Windows.Forms.Button BtnPreArmedSetup;
        private System.Windows.Forms.GroupBox GbxRcsEngageCalControl;
        private System.Windows.Forms.Button BtnFireCancel;
        private System.Windows.Forms.Button BtnDownDecY;
        private System.Windows.Forms.Button BtnRightIncX;
        private System.Windows.Forms.Button BtnUpIncY;
        private System.Windows.Forms.Button BtnFire;
        private System.Windows.Forms.Button BtnLeftDecX;
        private System.Windows.Forms.TextBox TxtAutoEngageList;
        private System.Windows.Forms.Label LblAutoEngageList;
        private System.Windows.Forms.Label LblRcsEngageCalControl;
        private System.Windows.Forms.ComboBox CmbModeSelect;
        private System.Windows.Forms.TextBox TxtRcsTcpPort;
        private System.Windows.Forms.Label LblTcpPort;
    }
}

